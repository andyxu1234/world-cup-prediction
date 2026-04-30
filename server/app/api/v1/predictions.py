"""预测相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models.prediction import Prediction
from app.models.match import Match
from app.schemas.prediction import PredictionOut, FaceSlapOut
from app.core.cache import prediction_cache, compare_cache, face_slap_cache, get_or_set

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
            select(Prediction)
            .where(Prediction.match_id == match_id)
            .options(selectinload(Prediction.ai_model))
        )
        result = await db.execute(stmt)
        predictions = result.scalars().all()

        out = []
        for pred in predictions:
            out.append(PredictionOut(
                id=pred.id,
                match_id=pred.match_id,
                model_id=pred.model_id,
                model_name=pred.ai_model.name,
                model_avatar=pred.ai_model.avatar_url,
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
            select(Prediction)
            .where(Prediction.match_id == match_id)
            .options(selectinload(Prediction.ai_model))
        )
        result = await db.execute(stmt)
        predictions = result.scalars().all()

        # 统计预测分布
        result_counts = {"home_win": 0, "draw": 0, "away_win": 0}
        for pred in predictions:
            result_counts[pred.result] += 1

        return {
            "match_id": match_id,
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


@router.get("/face-slaps", response_model=List[FaceSlapOut])
async def get_face_slaps(
    sort: str = Query("latest", description="排序方式: latest/confidence/absurdity"),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """获取打脸合集
    - latest: 最新翻车（胜负+比分都错，按比赛时间倒序）
    - confidence: 高信心翻车（胜负+比分都错，按信心倒序）
    - absurdity: 比分离谱（比分错误，按比分离谱度倒序）
    """
    cache_key = f"face_slaps:{sort}:{limit}"

    async def fetch():
        from sqlalchemy import desc as sa_desc

        base_stmt = (
            select(Prediction)
            .join(Prediction.match)
            .where(Prediction.is_correct_result.isnot(None))
            .where(Prediction.confidence.isnot(None))
            .options(
                selectinload(Prediction.ai_model),
                selectinload(Prediction.match).selectinload(Match.home_team),
                selectinload(Prediction.match).selectinload(Match.away_team),
            )
        )

        if sort == "confidence":
            stmt = base_stmt.where(
                Prediction.is_correct_result == False,
                Prediction.is_correct_score == False,
            ).order_by(sa_desc(Prediction.confidence)).limit(limit)
        elif sort == "absurdity":
            score_absurdity_expr = (
                func.abs(Prediction.score_home - Match.home_score) +
                func.abs(Prediction.score_away - Match.away_score)
            )
            stmt = (
                base_stmt.where(Prediction.is_correct_score == False)
                .order_by(sa_desc(score_absurdity_expr))
                .limit(limit)
            )
        else:
            stmt = base_stmt.where(
                Prediction.is_correct_result == False,
                Prediction.is_correct_score == False,
            ).order_by(sa_desc(Match.match_time)).limit(limit)

        result = await db.execute(stmt)
        predictions = result.scalars().all()

        face_slaps = []
        for pred in predictions:
            match = pred.match
            score_diff = abs((match.home_score or 0) - (match.away_score or 0))
            face_slap_index = (pred.confidence or 5) * (score_diff + 1)
            score_absurdity = abs((pred.score_home or 0) - (match.home_score or 0)) + abs((pred.score_away or 0) - (match.away_score or 0))

            face_slaps.append(FaceSlapOut(
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
                face_slap_index=face_slap_index,
                score_absurdity=score_absurdity,
                match_time=match.match_time.isoformat() if match.match_time else None,
            ))

        return face_slaps

    return await get_or_set(face_slap_cache, cache_key, fetch)
