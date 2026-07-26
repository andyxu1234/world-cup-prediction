"""赔率同步服务 — 拉取 Highlightly /odds 并落库到 match_odds 表

设计要点：
- 按 matchId 调一次 GET /odds 即可拿回该场所有博彩公司赔率（每场仅 1 次 API 调用）。
- 仅保留 is_active=True 的博彩公司（bookmakers 种子为 10 家）。
- 仅保留 MARKET_WHITELIST 内的核心市场（胜平负/双方进球/大小球主盘），
  过滤掉 Correct Score、Asian Handicap 各档、Total Cards/Corners 等噪音市场以控量。
- 追加式每日快照：落库用 MySQL INSERT ... ON DUPLICATE KEY UPDATE，
  唯一键为 (match_id, bookmaker_id, odds_type, market, value, snapshot_date)。
  同一天多次拉取覆盖当天值（幂等）；跨天则追加新快照，从而累积赔率走势。
- 单场失败不中断其他比赛（对齐预测流程的容错思路）。
- 短生命周期 session：DB 读取与 API 调用分开，避免长占用连接。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.config import get_settings
from app.core.highlightly import HighlightlyClient
from app.database import async_session_factory
from app.models.match import Match, MatchStatus
from app.models.odds import MatchOdd, OddsType


# 活跃博彩公司白名单（与 Alembic 种子一致），作为 bookmakers 表为空时的回退
ACTIVE_BOOKMAKER_IDS: set[int] = {4, 319, 11, 3, 10, 66, 23, 55, 17, 9}

# 市场白名单：只保留对走势分析有价值的核心市场（名称须与 API 返回完全一致）。
# 接口实测共 163 个细分市场，其余（Correct Score 全比分、Asian Handicap 各档、
# Total Cards/Corners、Odd or Even 等）对赔率走势是噪音，一律过滤以控制数据量。
MARKET_WHITELIST: set[str] = {
    "Full Time Result",   # 胜平负（Home / Draw / Away）
    "Both Teams To Score",  # 双方进球（Yes / No）
    "Total Goals 1.5",    # 大小球 1.5（Over / Under）
    "Total Goals 2.5",    # 大小球 2.5（主盘）
    "Total Goals 3.5",    # 大小球 3.5
}


async def _get_active_bookmaker_ids() -> set[int]:
    """读取 bookmakers 表中 is_active=True 的 highlightly_bookmaker_id 集合"""
    from app.models.odds import Bookmaker

    async with async_session_factory() as session:
        stmt = select(Bookmaker.highlightly_bookmaker_id).where(Bookmaker.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        ids = {row[0] for row in result.all()}
    return ids or ACTIVE_BOOKMAKER_IDS


async def sync_odds_for_match(
    client: HighlightlyClient,
    match_id: int,
    highlightly_id: int,
    active_bookmaker_ids: set[int],
    snapshot_date: date,
    snapshot_hour: int = 0,
    odds_type: str = "prematch",
) -> tuple[int, Optional[str]]:
    """同步单场比赛的赔率并按快照(日期+小时桶) upsert 落库。

    Args:
        client: 已实例化的 HighlightlyClient
        match_id: 本地比赛 ID（match_odds.match_id 外键）
        highlightly_id: Highlightly 比赛 ID（API matchId）
        active_bookmaker_ids: 需要保留的博彩公司白名单
        snapshot_date: 本次快照日期（同一批次统一，跨天追加走势）
        snapshot_hour: 本次快照小时桶(0-23)，每小时一个赔率点，用于日内走势
        odds_type: prematch / live

    Returns:
        (写入条数, 错误信息或 None)
    """
    # 1) 拉取赔率（单场一次调用）
    try:
        data = await client.get_odds(match_id=highlightly_id, odds_type=odds_type)
    except Exception as e:
        return 0, f"get_odds failed: {type(e).__name__}: {str(e)[:200]}"

    if not data or not data.get("data"):
        return 0, "no data (404/empty)"

    # 单场查询返回恰好一个 match 块
    block = data["data"][0]
    odds_list = block.get("odds", [])
    if not odds_list:
        return 0, "no odds entries"

    # 2) 展平为行，按白名单过滤
    rows: list[dict] = []
    for entry in odds_list:
        bid = entry.get("bookmakerId")
        if bid not in active_bookmaker_ids:
            continue
        bname = entry.get("bookmakerName", "")
        otype_raw = entry.get("type", odds_type)
        try:
            otype_enum = OddsType(otype_raw)
        except ValueError:
            otype_enum = OddsType(odds_type)
        market = entry.get("market", "")
        # 只保留白名单内的核心市场（控量 + 聚焦走势）
        if not market or market not in MARKET_WHITELIST:
            continue
        for v in entry.get("values", []):
            val = v.get("value", "")
            odd_val = v.get("odd")
            if not val or odd_val is None:
                continue
            try:
                odd_float = float(odd_val)
            except (TypeError, ValueError):
                continue
            rows.append({
                "match_id": match_id,
                "bookmaker_id": bid,
                "bookmaker_name": bname,
                "odds_type": otype_enum,
                "market": market,
                "value": val,
                "odd": odd_float,
                "snapshot_date": snapshot_date,
                "snapshot_hour": snapshot_hour,
            })

    if not rows:
        return 0, None  # 成功但无符合条件的数据

    # 3) 追加式快照 upsert：同一天(snapshot_date)覆盖，跨天追加
    stmt = mysql_insert(MatchOdd).values(rows)
    stmt = stmt.on_duplicate_key_update(
        odd=stmt.inserted.odd,
        bookmaker_name=stmt.inserted.bookmaker_name,
        fetched_at=func.now(),
    )
    async with async_session_factory() as session:
        await session.execute(stmt)
        await session.commit()

    return len(rows), None


async def sync_all_upcoming_odds(odds_type: str = "prematch") -> dict:
    """同步所有赛前窗口内（upcoming 且 7 天内）比赛的赔率。

    由 scheduler 每日调用（默认 04:00）。返回统计信息。
    """
    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )

    try:
        # 活跃博彩公司白名单
        active_ids = await _get_active_bookmaker_ids()

        # 本批次统一快照（UTC，与 horizon 口径一致）
        # snapshot_date 用于按天聚合走势；snapshot_hour 为小时桶(0-23)，
        # 每小时一个赔率点，保证同一小时多次运行幂等、跨小时追加走势。
        now_utc = datetime.now(timezone.utc)
        snapshot_date = now_utc.date()
        snapshot_hour = now_utc.hour

        # 赛前 7 天内的 upcoming 比赛（highlightly_id 必须存在）
        horizon = datetime.now(timezone.utc) + timedelta(days=7)
        async with async_session_factory() as session:
            stmt = (
                select(Match.id, Match.highlightly_id)
                .where(
                    Match.highlightly_id.isnot(None),
                    Match.status == MatchStatus.upcoming,
                    Match.match_time <= horizon,
                )
            )
            result = await session.execute(stmt)
            matches = result.all()

        if not matches:
            logger.info("sync_all_upcoming_odds: no upcoming matches in window, skipped")
            return {"status": "skipped", "reason": "no upcoming matches", "synced": 0, "failed": 0}

        success = 0
        failed = 0
        failed_details: list[dict] = []
        total_written = 0

        for match_id, highlightly_id in matches:
            written, err = await sync_odds_for_match(
                client=client,
                match_id=match_id,
                highlightly_id=highlightly_id,
                active_bookmaker_ids=active_ids,
                snapshot_date=snapshot_date,
                snapshot_hour=snapshot_hour,
                odds_type=odds_type,
            )
            if err:
                failed += 1
                failed_details.append({"match_id": match_id, "highlightly_id": highlightly_id, "error": err})
                logger.warning(f"Odds sync failed for match {match_id} (hl={highlightly_id}): {err}")
            else:
                success += 1
                total_written += written

        logger.info(
            f"sync_all_upcoming_odds done: {success} ok, {failed} failed, "
            f"{total_written} odds rows written (odds_type={odds_type})"
        )
        return {
            "status": "ok",
            "odds_type": odds_type,
            "snapshot_date": snapshot_date.isoformat(),
            "total": len(matches),
            "synced": success,
            "failed": failed,
            "written": total_written,
            "failed_details": failed_details[:10],
        }
    finally:
        await client.close()


async def sync_league_odds(league_id: int, odds_type: str = "prematch") -> dict:
    """同步指定联赛全部比赛的赔率（一次性拉全量，不限状态/时间窗口）。

    与 sync_all_upcoming_odds 的区别：按 league_id 过滤，且不限 status、
    不限未来 7 天窗口，用于补齐历史赛事（如已结束的世界杯）的完整赔率快照。
    逐场复用 sync_odds_for_match（含博彩公司白名单、市场白名单、快照 upsert）。
    """
    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )
    try:
        active_ids = await _get_active_bookmaker_ids()
        now_utc = datetime.now(timezone.utc)
        snapshot_date = now_utc.date()
        snapshot_hour = now_utc.hour

        # 该联赛下所有 highlightly_id 非空的比赛，不限 status / 时间
        async with async_session_factory() as session:
            stmt = (
                select(Match.id, Match.highlightly_id)
                .where(
                    Match.highlightly_id.isnot(None),
                    Match.league_id == league_id,
                )
            )
            result = await session.execute(stmt)
            matches = result.all()

        if not matches:
            logger.info(f"sync_league_odds: no matches for league_id={league_id}, skipped")
            return {
                "status": "skipped",
                "reason": "no matches for league",
                "league_id": league_id,
                "synced": 0,
                "failed": 0,
                "skipped": 0,
            }

        success = 0
        failed = 0
        skipped = 0
        failed_details: list[dict] = []
        total_written = 0

        for match_id, highlightly_id in matches:
            written, err = await sync_odds_for_match(
                client=client,
                match_id=match_id,
                highlightly_id=highlightly_id,
                active_bookmaker_ids=active_ids,
                snapshot_date=snapshot_date,
                snapshot_hour=snapshot_hour,
                odds_type=odds_type,
            )
            if err:
                # 404 / 无赔率属于正常跳过，不计入失败
                if err.startswith("no data") or err.startswith("no odds"):
                    skipped += 1
                    logger.info(
                        f"Odds skipped for match {match_id} (hl={highlightly_id}): {err}"
                    )
                else:
                    failed += 1
                    failed_details.append(
                        {"match_id": match_id, "highlightly_id": highlightly_id, "error": err}
                    )
                    logger.warning(
                        f"Odds sync failed for match {match_id} (hl={highlightly_id}): {err}"
                    )
            else:
                success += 1
                total_written += written
                if written == 0:
                    skipped += 1

        logger.info(
            f"sync_league_odds done: league_id={league_id}, {success} ok, "
            f"{failed} failed, {skipped} skipped, {total_written} odds rows written "
            f"(odds_type={odds_type})"
        )
        return {
            "status": "ok",
            "odds_type": odds_type,
            "league_id": league_id,
            "snapshot_date": snapshot_date.isoformat(),
            "total": len(matches),
            "synced": success,
            "failed": failed,
            "skipped": skipped,
            "written": total_written,
            "failed_details": failed_details[:10],
        }
    finally:
        await client.close()
