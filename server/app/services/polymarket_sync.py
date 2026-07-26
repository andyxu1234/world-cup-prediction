"""Polymarket 赛事同步服务

从 Polymarket Gamma API 拉取五大联赛 + 欧冠 + 欧联、未来 N 天内的比赛，
只取"胜负平"（moneyline 3-way）市场，分别 upsert 进：
  - polymarket_events  （一行 = 一场比赛：联赛/主客队/开球时间）
  - polymarket_markets （一行 = 一条腿：home/draw/away 的最新隐含概率）

拉取完成后立即调用 match_polymarket_events() 做本地 matches 匹配回填（match_id）；
匹配失败不影响已落库事件。仅只读拉取落库，不涉及任何交易/下单。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.polymarket import fetch_upcoming_moneyline
from app.database import async_session_factory
from app.models.polymarket_event import PolymarketEvent, PolymarketMarket
from app.services.polymarket_match import match_polymarket_events


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts_to_naive_utc(ts: float) -> Optional[datetime]:
    if not ts or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


async def _upsert_event(session: AsyncSession, ev: dict, now: datetime) -> PolymarketEvent:
    """按 slug upsert 一场比赛，返回持久化后的 PolymarketEvent（含 id）。"""
    slug = ev["slug"]
    row = (
        await session.execute(
            select(PolymarketEvent).where(PolymarketEvent.slug == slug)
        )
    ).scalar_one_or_none()

    is_new = row is None
    if row is None:
        row = PolymarketEvent(slug=slug)
        session.add(row)

    row.pm_event_id = ev.get("event_id") or None
    row.title = ev.get("title") or ""
    row.series_id = ev.get("series_id") or ""
    row.series_name = ev.get("series_name") or None
    row.home_team_raw = ev.get("home_team") or None
    row.away_team_raw = ev.get("away_team") or None
    row.game_start_time = _ts_to_naive_utc(ev.get("game_start_ts") or 0)
    row.market_count = len(ev.get("markets") or [])
    row.last_synced_at = now
    # match_id 不在此处理：留给后续单独的匹配任务回填

    await session.flush()  # 拿到 row.id 供 markets 外键使用
    logger.info(
        f"[Polymarket] {'新建' if is_new else '更新'} event: {slug} | "
        f"{row.title} ({row.home_team_raw} vs {row.away_team_raw}) @ {row.game_start_time}"
    )
    return row


async def _upsert_markets(
    session: AsyncSession, event_row: PolymarketEvent, markets: list, now: datetime
) -> int:
    """按 pm_market_id upsert 该比赛的胜负平腿，返回写入条数。"""
    count = 0
    for mk in markets:
        pm_id = str(mk.get("pm_market_id") or "")
        if not pm_id:
            continue
        row = (
            await session.execute(
                select(PolymarketMarket).where(PolymarketMarket.pm_market_id == pm_id)
            )
        ).scalar_one_or_none()
        is_new = row is None
        if row is None:
            row = PolymarketMarket(pm_market_id=pm_id, event_id=event_row.id, outcome="")
            session.add(row)
        row.event_id = event_row.id
        row.condition_id = mk.get("condition_id") or None
        row.clob_token_id_yes = mk.get("clob_token_id_yes") or None
        row.clob_token_id_no = mk.get("clob_token_id_no") or None
        row.position_id_yes = mk.get("position_id_yes") or None
        row.position_id_no = mk.get("position_id_no") or None
        row.question = (mk.get("question") or "")[:255] or None
        row.outcome = mk.get("outcome") or ""
        row.outcome_team = mk.get("outcome_team") or None
        row.price = mk.get("price")
        row.volume = mk.get("volume")
        row.liquidity = mk.get("liquidity")
        row.last_synced_at = now
        logger.info(
            f"[Polymarket] {'新建' if is_new else '更新'} market leg: {pm_id} | "
            f"{row.outcome} price={row.price} vol={row.volume} liq={row.liquidity}"
        )
        count += 1
    return count


async def sync_polymarket_events() -> dict:
    """拉取 Polymarket 未来 N 天的比赛 + 胜负平市场并落库。

    Returns:
        {"total_events": int, "total_markets": int, "series": [ {series, events, markets} ... ]}
    """
    settings = get_settings()
    series = settings.POLYMARKET_SERIES
    days_ahead = int(getattr(settings, "POLYMARKET_DAYS_AHEAD", 7))

    total_events = 0
    total_markets = 0
    per_series: list[dict] = []

    async with async_session_factory() as session:
        for s in series:
            sid = str(s.get("id", ""))
            sname = s.get("name", "")
            if not sid:
                continue
            logger.info(f"[Polymarket] 开始拉取 series: {sname} ({sid})")
            try:
                events = await fetch_upcoming_moneyline(sid, sname, days_ahead=days_ahead)
            except Exception as e:
                logger.warning(f"polymarket series {sid} ({sname}) fetch failed: {e}")
                per_series.append({"series": sname, "error": str(e)})
                continue
            if not events:
                per_series.append({"series": sname, "events": 0, "markets": 0})
                continue

            now = _utcnow_naive()
            s_markets = 0
            for ev in events:
                event_row = await _upsert_event(session, ev, now)
                s_markets += await _upsert_markets(session, event_row, ev.get("markets") or [], now)

            await session.commit()
            total_events += len(events)
            total_markets += s_markets
            per_series.append({"series": sname, "events": len(events), "markets": s_markets})
            logger.info(
                f"Polymarket synced {sname}: {len(events)} events, {s_markets} moneyline legs"
            )

    # 拉取完成后立即做本地匹配回填（match_id），失败不影响已落库事件
    try:
        match_summary = await match_polymarket_events()
    except Exception as e:
        logger.error(f"[Polymarket] 匹配步骤失败（不影响已落库事件）: {e}")
        match_summary = None

    return {
        "total_events": total_events,
        "total_markets": total_markets,
        "series": per_series,
        "match": match_summary,
    }
