"""Polymarket 事件 ↔ 本地 matches 匹配服务

把 polymarket_events.match_id IS NULL 的比赛，交给 DeepSeek 按「联赛 + 比赛时间」
与本地 matches 匹配，写回 match_id。

分工：
- 代码负责「按联赛 + 时间窗捞出候选 matches」——DeepSeek 不能直接执行 SQL；
- DeepSeek 负责「在候选内挑选 match_id」（主依据 kickoff 时间，队名作佐证）；
- 代码负责「校验 + 落地 + 防幻觉」：只接受候选集内的 match_id，越界/None 留 NULL。
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ofoxai import OfoxAIClient
from app.database import async_session_factory
from app.models.polymarket_event import PolymarketEvent
from app.models.match import Match
from app.models.team import Team
from app.models.league import League
from app.models.ai_model import AIModel

# 候选比赛时间窗边距（天）：在 Polymarket 事件 kickoff(北京) 基础上前后各扩这么多，
# 用于预过滤本地 matches 候选集；DeepSeek 仍在候选内精确匹配。
_POLYMATCH_CANDIDATE_MARGIN_DAYS = 3

# DeepSeek 调用兜底模型（若 ai_models 表无活跃 DeepSeek 时使用）
_FALLBACK_DEEPSEEK_MODEL = "deepseek/deepseek-v3.2"


def _beijing_str(utc_dt) -> str:
    """Polymarket game_start_time(UTC) -> 北京时间字符串，便于和本地 match_time(北京) 直接比较。"""
    if utc_dt is None:
        return ""
    return (utc_dt + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


async def _resolve_series_league_map(session: AsyncSession) -> dict[str, int]:
    """series_id -> 本地 leagues.id（2026 赛季活跃行）。"""
    settings = get_settings()
    raw = getattr(settings, "POLYMARKET_SERIES_LEAGUE", {}) or {}
    result: dict[str, int] = {}
    for series_id, hl_id in raw.items():
        lid = (
            await session.execute(
                select(League.id).where(
                    League.highlightly_league_id == int(hl_id),
                    League.season == 2026,
                )
            )
        ).scalar_one_or_none()
        if lid is None:
            logger.warning(
                f"[PolymarketMatch] series {series_id} (highlightly {hl_id}) 未找到 2026 联赛行，跳过"
            )
            continue
        result[series_id] = lid
    return result


async def _resolve_deepseek_model(session: AsyncSession) -> str:
    """复用预测汇总的 DeepSeek 模型（与 ai_models 表活跃 DeepSeek 一致）。"""
    row = (
        await session.execute(
            select(AIModel.model_id).where(
                AIModel.name == "DeepSeek", AIModel.is_active == True
            )
        )
    ).scalar_one_or_none()
    return row if row else _FALLBACK_DEEPSEEK_MODEL


def _build_messages(events, candidates, team_names, league_name) -> list[dict]:
    list_a = [
        {
            "slug": e.slug,
            "home_team": e.home_team_raw,
            "away_team": e.away_team_raw,
            "kickoff_beijing": _beijing_str(e.game_start_time),
            "competition": e.series_name,
        }
        for e in events
    ]
    list_b = [
        {
            "match_id": c["match_id"],
            "home_team": team_names.get(c["home_team_id"]) or "",
            "away_team": team_names.get(c["away_team_id"]) or "",
            "kickoff_beijing": c["kickoff_beijing"],
            "competition": league_name,
        }
        for c in candidates
    ]
    system = (
        "You are a football data matching assistant. "
        "You will receive two lists of football matches. "
        "List A contains matches from Polymarket (a prediction market). "
        "List B contains matches from our local database for the SAME competition. "
        "All kickoff times are already normalized to Beijing time (UTC+8) for direct comparison. "
        "Your job: for each match in List A, find the single best matching match_id from List B, "
        "using primarily the kickoff time (should match exactly or within a few minutes) and "
        "secondarily the team names. "
        "Return ONLY a JSON object mapping each List A 'slug' to either the matched 'match_id' "
        "(integer) from List B, or null if no confident match exists. "
        "You MUST only use match_ids that appear in List B. Do not invent ids. "
        "Example output: {\"slug-a\": 123, \"slug-b\": null}"
    )
    user = (
        f"List A (Polymarket events to match, competition={league_name}):\n"
        f"{json.dumps(list_a, ensure_ascii=False, indent=2)}\n\n"
        f"List B (local candidate matches):\n"
        f"{json.dumps(list_b, ensure_ascii=False, indent=2)}\n\n"
        "Return the JSON mapping now."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def _match_one_league(
    session: AsyncSession,
    client: OfoxAIClient,
    model_id: str,
    series_id: str,
    league_id: int,
    league_name: str,
) -> dict:
    # 1) 待匹配事件
    events = (
        await session.execute(
            select(PolymarketEvent).where(
                PolymarketEvent.series_id == series_id,
                PolymarketEvent.match_id.is_(None),
            )
        )
    ).scalars().all()
    if not events:
        return {"series_id": series_id, "events": 0, "matched": 0, "failed": 0}

    # 2) 时间窗（北京）：基于事件 kickoff 前后扩边距
    utc_times = [e.game_start_time for e in events if e.game_start_time]
    if not utc_times:
        logger.info(f"[PolymarketMatch] 事件均无 kickoff，全部未匹配 series {series_id}")
        return {"series_id": series_id, "events": len(events), "matched": 0, "failed": len(events)}
    margin = timedelta(days=_POLYMATCH_CANDIDATE_MARGIN_DAYS)
    lo_bj = (min(utc_times) + timedelta(hours=8)) - margin
    hi_bj = (max(utc_times) + timedelta(hours=8)) + margin

    candidate_rows = (
        await session.execute(
            select(
                Match.id,
                Match.home_team_id,
                Match.away_team_id,
                Match.match_time,
            ).where(
                Match.league_id == league_id,
                Match.match_time >= lo_bj,
                Match.match_time <= hi_bj,
            )
        )
    ).all()

    if not candidate_rows:
        logger.info(f"[PolymarketMatch] 候选为空，全部未匹配 series {series_id}")
        return {"series_id": series_id, "events": len(events), "matched": 0, "failed": len(events)}

    # 3) 队名映射
    team_ids = set()
    for r in candidate_rows:
        if r.home_team_id:
            team_ids.add(r.home_team_id)
        if r.away_team_id:
            team_ids.add(r.away_team_id)
    team_names: dict[int, str] = {}
    if team_ids:
        trows = (
            await session.execute(select(Team.id, Team.name).where(Team.id.in_(team_ids)))
        ).all()
        team_names = {tid: name for tid, name in trows}

    candidates = [
        {
            "match_id": r.id,
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "kickoff_beijing": r.match_time.strftime("%Y-%m-%d %H:%M") if r.match_time else "",
        }
        for r in candidate_rows
    ]
    candidate_ids = {c["match_id"] for c in candidates}

    # 4) 调 DeepSeek
    messages = _build_messages(events, candidates, team_names, league_name)
    try:
        content = await client.chat_completion(
            model=model_id, messages=messages, temperature=0.0, max_tokens=4096
        )
    except Exception as exc:
        logger.error(f"[PolymarketMatch] DeepSeek 调用失败 series {series_id}: {exc}")
        return {"series_id": series_id, "events": len(events), "matched": 0, "failed": len(events)}

    parsed = OfoxAIClient._extract_json(content)
    if not isinstance(parsed, dict):
        logger.error(
            f"[PolymarketMatch] DeepSeek 返回非 JSON 对象 series {series_id}: {content[:200]!r}"
        )
        return {"series_id": series_id, "events": len(events), "matched": 0, "failed": len(events)}

    # 5) 校验 + 落地（防幻觉：只接受候选集内的 match_id）
    matched = 0
    failed = 0
    for e in events:
        val = parsed.get(e.slug)
        if val is None or val == "" or val == "null":
            logger.info(f"[PolymarketMatch] 未匹配(DeepSeek=null): {e.slug}")
            failed += 1
            continue
        try:
            mid = int(val)
        except (TypeError, ValueError):
            logger.warning(f"[PolymarketMatch] 非法 match_id 值 slug={e.slug} val={val!r}")
            failed += 1
            continue
        if mid not in candidate_ids:
            logger.warning(
                f"[PolymarketMatch] DeepSeek 返回越界 match_id {mid} (不在候选集) slug={e.slug}"
            )
            failed += 1
            continue
        e.match_id = mid
        matched += 1
        logger.info(f"[PolymarketMatch] 匹配成功: {e.slug} -> match_id {mid}")

    await session.commit()
    return {
        "series_id": series_id,
        "events": len(events),
        "matched": matched,
        "failed": failed,
    }


async def match_polymarket_events() -> dict:
    """把 polymarket_events.match_id IS NULL 的比赛交给 DeepSeek 匹配本地 matches。

    代码按联赛 + 时间窗捞出候选 matches，DeepSeek 在候选内挑选 match_id；
    匹配结果写回 polymarket_events.match_id，无匹配/越界留 NULL。
    """
    settings = get_settings()
    summary: dict = {
        "total_events": 0,
        "total_matched": 0,
        "total_failed": 0,
        "leagues": [],
    }
    async with async_session_factory() as session:
        series_map = await _resolve_series_league_map(session)
        if not series_map:
            logger.warning("[PolymarketMatch] 未解析到任何 series->league 映射，退出")
            return summary

        league_names = {}
        lrows = (
            await session.execute(
                select(League.id, League.name).where(League.id.in_(series_map.values()))
            )
        ).all()
        league_names = {lid: name for lid, name in lrows}

        client = OfoxAIClient(api_key=settings.OFOXAI_API_KEY, base_url=settings.OFOXAI_BASE_URL)
        model_id = await _resolve_deepseek_model(session)
        logger.info(f"[PolymarketMatch] 使用 DeepSeek 模型: {model_id}")

        try:
            for series_id, league_id in series_map.items():
                res = await _match_one_league(
                    session,
                    client,
                    model_id,
                    series_id,
                    league_id,
                    league_names.get(league_id, ""),
                )
                summary["leagues"].append(res)
                summary["total_events"] += res["events"]
                summary["total_matched"] += res["matched"]
                summary["total_failed"] += res["failed"]
        finally:
            await client.close()

    logger.info(
        f"[PolymarketMatch] 完成: events={summary['total_events']} "
        f"matched={summary['total_matched']} failed={summary['total_failed']}"
    )
    return summary
