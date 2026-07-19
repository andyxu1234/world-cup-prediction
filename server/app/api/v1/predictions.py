"""预测相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.database import get_db
from app.models.prediction import Prediction
from app.models.match import Match
from app.schemas.prediction import PredictionOut
from app.core.cache import prediction_cache, compare_cache, get_or_set

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/match/{match_id}", response_model=List[PredictionOut])
async def get_match_predictions(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取某场比赛所有 AI 预测"""
    cache_key = f"match_pred:{match_id}"

    async def fetch():
        stmt = (
            select(Prediction, Match)
            .join(Match, Match.id == Prediction.match_id)
            .where(Prediction.match_id == match_id)
            .options(selectinload(Prediction.ai_model))
        )
        result = await db.execute(stmt)
        rows = result.all()
        predictions = [r[0] for r in rows]
        league_id = rows[0][1].league_id if rows else None

        out = []
        for pred in predictions:
            out.append(PredictionOut(
                id=pred.id,
                match_id=pred.match_id,
                model_id=pred.model_id,
                model_name=pred.ai_model.name,
                model_avatar=pred.ai_model.avatar_url,
                league_id=league_id,
                result=pred.result,
                score_home=pred.score_home,
                score_away=pred.score_away,
                score_alt_home=pred.score_alt_home,
                score_alt_away=pred.score_alt_away,
                score_alt_prob=pred.score_alt_prob,
                confidence=pred.confidence,
                analysis=pred.analysis,
                is_correct_result=pred.is_correct_result,
                is_correct_score=pred.is_correct_score,
                created_at=pred.created_at,
            ))
        return out

    return await get_or_set(prediction_cache, cache_key, fetch)


@router.get("/compare/{match_id}", response_model=dict)
async def compare_predictions(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """预测对比视图数据"""
    cache_key = f"pred_compare:{match_id}"

    async def fetch():
        stmt = (
            select(Prediction, Match)
            .join(Match, Match.id == Prediction.match_id)
            .where(Prediction.match_id == match_id)
            .options(selectinload(Prediction.ai_model))
        )
        result = await db.execute(stmt)
        rows = result.all()
        predictions = [r[0] for r in rows]
        league_id = rows[0][1].league_id if rows else None

        # 统计预测分布
        result_counts = {"home_win": 0, "draw": 0, "away_win": 0}
        for pred in predictions:
            result_counts[pred.result] += 1

        return {
            "match_id": match_id,
            "league_id": league_id,
            "result_distribution": result_counts,
            "predictions": [
                {
                    "model_name": p.ai_model.name,
                    "result": p.result.value if hasattr(p.result, 'value') else str(p.result),
                    "score": f"{p.score_home or 0}:{p.score_away or 0}",
                    "score_alt": f"{p.score_alt_home or 0}:{p.score_alt_away or 0}" if (p.score_alt_home is not None and p.score_alt_away is not None) else None,
                    "score_alt_prob": float(p.score_alt_prob) * 100 if p.score_alt_prob else None,
                    "confidence": p.confidence,
                    "analysis": p.analysis,
                }
                for p in predictions
            ],
        }

    return await get_or_set(compare_cache, cache_key, fetch)
