"""缓存预热服务

每 5 分钟由 scheduler 调用，主动查询数据库填充缓存，
确保绝大多数请求直接命中缓存，不查数据库。
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.cache import (
    stats_cache, matches_cache, match_detail_cache,
    prediction_cache, compare_cache,
    leaderboard_cache,
    clear_all_caches, get_cache_stats,
)
from app.database import async_session_factory
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.ai_model import AIModel
from app.models.user_vote import UserVote
from app.services.leaderboard_calc import get_ai_leaderboard, get_human_leaderboard


async def refresh_all_caches():
    """刷新所有只读缓存（由 scheduler 每 5 分钟调用）"""
    logger.info("[CacheWarmer] Starting cache refresh...")

    # 先清空只读缓存，确保数据新鲜
    for cache in [stats_cache, matches_cache, match_detail_cache,
                  prediction_cache, compare_cache,
                  leaderboard_cache]:
        cache.clear()

    async with async_session_factory() as db:
        try:
            # 1. 首页统计
            total_matches = (await db.execute(select(func.count(Match.id)))).scalar() or 0
            active_ai = (await db.execute(
                select(func.count(AIModel.id)).where(AIModel.is_active == True)
            )).scalar() or 0
            total_predictions = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0
            total_users = (await db.execute(
                select(func.count(func.distinct(UserVote.user_id)))
            )).scalar() or 0
            total_user_predictions = (await db.execute(select(func.count(UserVote.id)))).scalar() or 0
            from app.schemas.match import HomeStatsOut
            stats_cache["home_stats"] = HomeStatsOut(
                total_matches=total_matches,
                active_ai_models=active_ai,
                total_predictions=total_predictions,
                total_users=total_users,
                total_user_predictions=total_user_predictions,
            )
            logger.debug("[CacheWarmer] stats cached")

            # 2. 比赛列表（默认查询：全部）
            stmt = (
                select(Match)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.summary),
                )
                .order_by(Match.match_time)
            )
            result = await db.execute(stmt)
            matches_cache["matches:None:None:None:None"] = result.scalars().all()
            logger.debug("[CacheWarmer] matches cached")

            # 3. 排行榜（默认参数）
            await get_ai_leaderboard(db, round_filter="全部", sort_by="result_accuracy", sort_order="desc", league_ids=None)
            await get_human_leaderboard(db, current_user_id=None, round_filter="全部", league_ids=None)
            logger.debug("[CacheWarmer] leaderboard cached")

            # 4. 排行榜（默认参数）已在上面完成；此处无长期预测逻辑

        except Exception as e:
            logger.error(f"[CacheWarmer] Error during cache refresh: {e}")
            # 不抛出异常，避免影响 scheduler

    stats = get_cache_stats()
    logger.info(
        f"[CacheWarmer] Refresh done. "
        f"hits={stats['hits']} misses={stats['misses']} rate={stats['hit_rate']}%"
    )
