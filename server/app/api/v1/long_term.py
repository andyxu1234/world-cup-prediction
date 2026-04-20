"""长期预测路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models.long_term_prediction import LongTermPrediction
from app.schemas.long_term_prediction import LongTermPredictionOut

router = APIRouter(prefix="/long-term-predictions", tags=["long-term-predictions"])


@router.get("", response_model=List[LongTermPredictionOut])
async def get_long_term_predictions(
    db: AsyncSession = Depends(get_db),
):
    """获取冠亚季军预测"""
    stmt = (
        select(LongTermPrediction)
        .options(
            selectinload(LongTermPrediction.ai_model),
            selectinload(LongTermPrediction.champion_team),
            selectinload(LongTermPrediction.runner_up_team),
            selectinload(LongTermPrediction.third_place_team),
        )
    )
    result = await db.execute(stmt)
    predictions = result.scalars().all()

    out = []
    for pred in predictions:
        out.append(LongTermPredictionOut(
            model_id=pred.model_id,
            model_name=pred.ai_model.name if pred.ai_model else None,
            champion=pred.champion_team.name if pred.champion_team else None,
            runner_up=pred.runner_up_team.name if pred.runner_up_team else None,
            third_place=pred.third_place_team.name if pred.third_place_team else None,
            analysis=pred.analysis,
        ))
    return out
