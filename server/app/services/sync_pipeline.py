"""同步编排服务 — 事件驱动的数据同步流水线

核心入口：sync_matches_and_respond()
每 30 分钟由 scheduler 调用，根据 sync_matches 返回的变更信息，
自动触发下游的 H2H 同步、球队统计更新、预测评估等操作。
"""

from __future__ import annotations

import asyncio
from loguru import logger

from app.services.match_sync import sync_matches
from app.services.h2h_sync import sync_h2h_for_match
from app.services.stats_sync import sync_stats_for_teams
from app.services.prediction_evaluator import evaluate_predictions


async def sync_matches_and_respond():
    """每 30 分钟执行：同步比赛 + 事件驱动下游

    流程：
    1. sync_matches() — 同步比赛数据，返回新增/刚结束的比赛
    2. 新增比赛 → 同步该场比赛的 H2H
    3. 刚结束的比赛 → 更新涉及球队的 stats/form → 评估预测
    """
    logger.info("=== Sync pipeline started ===")

    # 1. 同步比赛数据
    try:
        result = await sync_matches()
    except Exception as e:
        logger.error(f"sync_matches failed, pipeline aborted: {e}")
        return {"status": "aborted", "reason": f"sync_matches failed: {e}"}

    new_matches = result.get("new_matches", [])
    newly_finished = result.get("newly_finished", [])

    h2h_synced = 0
    stats_synced = 0
    predictions_evaluated = False

    # 2. 新增比赛 → 同步 H2H
    if new_matches:
        logger.info(f"Pipeline: {len(new_matches)} new matches, syncing H2H...")
        h2h_synced = await _sync_h2h_for_new_matches(new_matches)

    # 3. 刚结束的比赛 → 更新球队 stats + 评估预测
    if newly_finished:
        logger.info(f"Pipeline: {len(newly_finished)} matches just finished, updating stats & evaluating...")
        stats_synced = await _respond_to_finished_matches(newly_finished)
        predictions_evaluated = True

    logger.info(
        f"=== Sync pipeline completed: "
        f"{result.get('synced', 0)} matches synced, "
        f"{h2h_synced} H2H synced, "
        f"{stats_synced} team stats updated, "
        f"predictions_evaluated={predictions_evaluated} ==="
    )

    return {
        "status": "ok",
        "synced": result.get("synced", 0),
        "new_matches": len(new_matches),
        "newly_finished": len(newly_finished),
        "h2h_synced": h2h_synced,
        "stats_synced": stats_synced,
        "predictions_evaluated": predictions_evaluated,
    }


# ── 内部编排逻辑 ─────────────────────────────────────────────

async def _sync_h2h_for_new_matches(highightly_ids: list[int]) -> int:
    """为新增的比赛同步 H2H 数据

    Args:
        highlightly_ids: Highlightly match ID 列表

    Note: 这里 highlightly_id 需要先转换为本地 match_id，
    但 sync_matches 返回的是 highlightly_id，需要查库转换。
    """
    from app.database import async_session_factory
    from app.models.match import Match
    from sqlalchemy import select

    # highlightly_id → 本地 match_id
    async with async_session_factory() as session:
        stmt = select(Match.id).where(Match.highlightly_id.in_(highightly_ids))
        result = await session.execute(stmt)
        local_match_ids = [row[0] for row in result.all()]

    if not local_match_ids:
        return 0

    # 逐个同步 H2H（每场比赛调一次 Highlightly API，串行避免限流）
    synced = 0
    for match_id in local_match_ids:
        try:
            ok = await sync_h2h_for_match(match_id)
            if ok:
                synced += 1
        except Exception as e:
            logger.warning(f"H2H sync failed for match {match_id}: {e}")

    return synced


async def _respond_to_finished_matches(highightly_ids: list[int]) -> int:
    """响应比赛结束事件：更新球队 stats + 评估预测

    Args:
        highlightly_ids: Highlightly match ID 列表

    Returns:
        更新的球队数量
    """
    from app.database import async_session_factory
    from app.models.match import Match
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # 获取刚结束比赛涉及的球队 ID（去重）
    async with async_session_factory() as session:
        stmt = (
            select(Match)
            .where(Match.highlightly_id.in_(highightly_ids))
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
        )
        result = await session.execute(stmt)
        matches = result.scalars().all()

        team_ids = set()
        for m in matches:
            team_ids.add(m.home_team_id)
            team_ids.add(m.away_team_id)

    # 更新涉及的球队 stats + recent_form
    stats_result = {"stats": 0, "form": 0}
    if team_ids:
        try:
            stats_result = await sync_stats_for_teams(list(team_ids))
        except Exception as e:
            logger.error(f"Stats update failed for finished matches: {e}")

    # 评估预测
    try:
        await evaluate_predictions()
    except Exception as e:
        logger.error(f"Prediction evaluation failed: {e}")

    return stats_result.get("stats", 0)
