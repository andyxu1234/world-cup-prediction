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
    prediction_cache, compare_cache, face_slap_cache,
    leaderboard_cache, long_term_cache, fun_fact_cache,
    clear_all_caches, get_cache_stats,
)
from app.database import async_session_factory
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.ai_model import AIModel
from app.models.user_vote import UserVote
from app.models.long_term_prediction import LongTermPrediction
from app.services.leaderboard_calc import get_ai_leaderboard, get_human_leaderboard


async def refresh_all_caches():
    """刷新所有只读缓存（由 scheduler 每 5 分钟调用）"""
    logger.info("[CacheWarmer] Starting cache refresh...")

    # 先清空只读缓存，确保数据新鲜
    for cache in [stats_cache, matches_cache, match_detail_cache,
                  prediction_cache, compare_cache, face_slap_cache,
                  leaderboard_cache, long_term_cache, fun_fact_cache]:
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
            await get_ai_leaderboard(db, round_filter="全部", sort_by="result_accuracy", sort_order="desc")
            await get_human_leaderboard(db, current_user_id=None, round_filter="全部")
            logger.debug("[CacheWarmer] leaderboard cached")

            # 4. 打脸合集（默认参数：只预热 latest）
            # 注意：必须构建 FaceSlapOut 对象存入缓存，与 API 端点返回类型一致
            from app.models.match import Match as M
            from app.schemas.prediction import FaceSlapOut
            base_stmt = (
                select(Prediction)
                .join(Prediction.match)
                .where(Prediction.is_correct_result.isnot(None))
                .where(Prediction.confidence.isnot(None))
                .options(
                    selectinload(Prediction.ai_model),
                    selectinload(Prediction.match).selectinload(M.home_team),
                    selectinload(Prediction.match).selectinload(M.away_team),
                )
            )
            from sqlalchemy import desc as sa_desc
            face_stmt = base_stmt.where(
                Prediction.is_correct_result == False,
                Prediction.is_correct_score == False,
            ).order_by(sa_desc(M.match_time)).limit(20)
            face_result = await db.execute(face_stmt)
            face_predictions = face_result.scalars().all()

            face_outs = []
            for pred in face_predictions:
                match = pred.match
                score_diff = abs((match.home_score or 0) - (match.away_score or 0))
                score_absurdity = abs((pred.score_home or 0) - (match.home_score or 0)) + abs((pred.score_away or 0) - (match.away_score or 0))
                face_outs.append(FaceSlapOut(
                    prediction_id=pred.id,
                    model_name=pred.ai_model.name,
                    model_avatar=pred.ai_model.avatar_url,
                    match_id=match.id,
                    home_team=match.home_team.cn_name or match.home_team.name,
                    away_team=match.away_team.cn_name or match.away_team.name,
                    home_team_flag=match.home_team.flag_url,
                    away_team_flag=match.away_team.flag_url,
                    predicted_result=pred.result,
                    predicted_score=f"{pred.score_home}:{pred.score_away}",
                    actual_result=match.result or "",
                    actual_score=f"{match.home_score}:{match.away_score}",
                    confidence=pred.confidence,
                    analysis=pred.analysis,
                    face_slap_index=(pred.confidence or 5) * (score_diff + 1),
                    score_absurdity=score_absurdity,
                    match_time=match.match_time.isoformat() if match.match_time else None,
                ))
            face_slap_cache["face_slaps:latest:20"] = face_outs
            logger.debug("[CacheWarmer] face-slaps cached")

            # 5. 长期预测
            lt_stmt = (
                select(LongTermPrediction)
                .options(
                    selectinload(LongTermPrediction.ai_model),
                    selectinload(LongTermPrediction.champion_team),
                    selectinload(LongTermPrediction.runner_up_team),
                    selectinload(LongTermPrediction.third_place_team),
                )
            )
            lt_result = await db.execute(lt_stmt)
            from app.schemas.long_term_prediction import LongTermPredictionOut
            lt_preds = lt_result.scalars().all()
            lt_out = []
            for pred in lt_preds:
                lt_out.append(LongTermPredictionOut(
                    model_id=pred.model_id,
                    model_name=pred.ai_model.name if pred.ai_model else None,
                    champion=pred.champion_team.name if pred.champion_team else None,
                    runner_up=pred.runner_up_team.name if pred.runner_up_team else None,
                    third_place=pred.third_place_team.name if pred.third_place_team else None,
                    analysis=pred.analysis,
                ))
            long_term_cache["long_term_predictions"] = lt_out
            logger.debug("[CacheWarmer] long-term predictions cached")

            # 6. 趣闻（触发 DeepSeek 生成，缓存1小时）
            try:
                from app.api.v1.fun_fact import _call_deepseek
                from app.api.v1.fun_fact import FunFactOut
                result = await _call_deepseek()
                fun_fact_cache["latest"] = FunFactOut(
                    icon=result.get("icon", "🎵"),
                    title=result.get("title", "你知道吗？"),
                    text=result.get("text", "精彩内容加载中..."),
                )
                logger.debug("[CacheWarmer] fun-fact cached")
            except Exception as fe:
                logger.warning(f"[CacheWarmer] fun-fact generation failed (non-fatal): {fe}")

        except Exception as e:
            logger.error(f"[CacheWarmer] Error during cache refresh: {e}")
            # 不抛出异常，避免影响 scheduler

    stats = get_cache_stats()
    logger.info(
        f"[CacheWarmer] Refresh done. "
        f"hits={stats['hits']} misses={stats['misses']} rate={stats['hit_rate']}%"
    )
