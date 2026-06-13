"""预测评估服务 — 比赛结束后评估 AI 预测准确性"""

from __future__ import annotations

from datetime import datetime
from loguru import logger

from app.database import async_session_factory
from app.models.match import Match, MatchStatus, MatchResult
from app.models.prediction import Prediction
from app.models.user_vote import UserVote


async def evaluate_predictions(force_recalculate: bool = False):
    """定时任务：评估已结束但尚未评估的比赛的预测

    Args:
        force_recalculate: 是否强制重新计算所有已评估的预测（用于修复计算逻辑）
    """
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select

            # 找出已结束但预测未评估的比赛
            stmt = (
                select(Match)
                .where(Match.status == MatchStatus.finished)
                .where(Match.result.isnot(None))
            )
            result = await session.execute(stmt)
            matches = result.scalars().all()

            evaluated_count = 0
            for match in matches:
                # 评估 AI 预测
                if force_recalculate:
                    # 强制重新计算：评估所有预测
                    pred_stmt = select(Prediction).where(
                        Prediction.match_id == match.id,
                    )
                else:
                    # 正常模式：只评估未评估的预测
                    pred_stmt = select(Prediction).where(
                        Prediction.match_id == match.id,
                        Prediction.is_correct_result.is_(None),
                    )
                pred_result = await session.execute(pred_stmt)
                predictions = pred_result.scalars().all()

                for pred in predictions:
                    pred.is_correct_result = (pred.result == match.result)
                    # 比分命中：主比分命中 OR 备选比分命中（任一命中即算命中）
                    main_score_hit = (
                        pred.score_home == match.home_score
                        and pred.score_away == match.away_score
                    )
                    alt_score_hit = (
                        pred.score_alt_home is not None
                        and pred.score_alt_away is not None
                        and pred.score_alt_home == match.home_score
                        and pred.score_alt_away == match.away_score
                    )
                    pred.is_correct_score = main_score_hit or alt_score_hit
                    pred.calculated_at = datetime.utcnow()
                    evaluated_count += 1

                # 评估用户投票
                vote_stmt = select(UserVote).where(
                    UserVote.match_id == match.id,
                    UserVote.is_correct_result.is_(None),
                )
                vote_result = await session.execute(vote_stmt)
                votes = vote_result.scalars().all()

                for vote in votes:
                    vote.is_correct_result = (vote.result == match.result)
                    vote.is_correct_score = (
                        vote.score_home == match.home_score
                        and vote.score_away == match.away_score
                    )

            await session.commit()

        logger.info(f"Evaluated {evaluated_count} predictions")
    except Exception as e:
        logger.error(f"Prediction evaluation failed: {e}")
