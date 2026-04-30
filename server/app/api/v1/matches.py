"""比赛相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List

from app.database import get_db
from app.deps import DBSession
from app.models.match import Match, MatchStatus
from app.models.prediction import Prediction
from app.models.prediction_summary import PredictionSummary
from app.models.ai_model import AIModel
from app.models.user_vote import UserVote
from app.schemas.match import MatchListOut, MatchDetailOut, PredictionSummaryOut, HomeStatsOut
from app.core.cache import stats_cache, matches_cache, match_detail_cache, get_or_set

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/stats", response_model=HomeStatsOut)
async def get_home_stats(db: AsyncSession = Depends(get_db)):
    """首页 Hero 区域统计数据"""
    async def fetch():
        total_matches = (await db.execute(select(func.count(Match.id)))).scalar() or 0
        active_ai = (await db.execute(
            select(func.count(AIModel.id)).where(AIModel.is_active == True)
        )).scalar() or 0
        total_predictions = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0
        total_users = (await db.execute(
            select(func.count(func.distinct(UserVote.user_id)))
        )).scalar() or 0
        total_user_predictions = (await db.execute(select(func.count(UserVote.id)))).scalar() or 0
        return HomeStatsOut(
            total_matches=total_matches,
            active_ai_models=active_ai,
            total_predictions=total_predictions,
            total_users=total_users,
            total_user_predictions=total_user_predictions,
        )
    return await get_or_set(stats_cache, "home_stats", fetch)


@router.get("", response_model=List[MatchListOut])
async def get_matches(
    round: Optional[List[str]] = Query(None, description="轮次筛选，支持多个，如 ?round=Group+Stage+-1&round=Round+of+16"),
    status: Optional[str] = Query(None, description="状态筛选"),
    status_not: Optional[str] = Query(None, description="状态排除筛选（排除指定状态）"),
    date: Optional[str] = Query(None, description="日期筛选，格式 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """获取比赛列表"""
    cache_key = f"matches:{round}:{status}:{status_not}:{date}"

    async def fetch():
        stmt = (
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.summary),
            )
            .order_by(Match.match_time)
        )
        if round:
            stmt = stmt.where(Match.round.in_(round))
        if status:
            stmt = stmt.where(Match.status == status)
        if status_not:
            stmt = stmt.where(Match.status != status_not)
        if date:
            # match_time 是 datetime 类型，用 DATE() 函数按天匹配
            from sqlalchemy import func as sa_func, cast
            from sqlalchemy.types import Date as SqlDate
            stmt = stmt.where(cast(Match.match_time, SqlDate) == sa_func.date(date))

        result = await db.execute(stmt)
        return result.scalars().all()

    return await get_or_set(matches_cache, cache_key, fetch)


@router.get("/{match_id}", response_model=MatchDetailOut)
async def get_match_detail(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取比赛详情（含各 AI 预测）"""
    cache_key = f"match_detail:{match_id}"

    async def fetch():
        stmt = (
            select(Match)
            .where(Match.id == match_id)
            .options(
                selectinload(Match.home_team), selectinload(Match.away_team),
                selectinload(Match.predictions).selectinload(Prediction.ai_model),
                selectinload(Match.summary),
            )
        )
        result = await db.execute(stmt)
        match = result.scalar_one_or_none()
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")

        # 转换为字典，排除 ORM 的 predictions（它是对象而非 dict），后面手动构建
        def _enumval(v):
            return v.value if hasattr(v, 'value') else v

        match_dict = {
            "id": match.id,
            "match_day": match.match_day,
            "round": match.round,
            "match_time": match.match_time,
            "venue": match.venue,
            "status": _enumval(match.status),
            "home_score": match.home_score,
            "away_score": match.away_score,
            "result": _enumval(match.result),
            "home_team": {"id": match.home_team.id, "name": match.home_team.name, "cn_name": match.home_team.cn_name, "flag_url": match.home_team.flag_url, "group_name": match.home_team.group_name, "fifa_rank": match.home_team.fifa_rank},
            "away_team": {"id": match.away_team.id, "name": match.away_team.name, "cn_name": match.away_team.cn_name, "flag_url": match.away_team.flag_url, "group_name": match.away_team.group_name, "fifa_rank": match.away_team.fifa_rank},
        }
        preds_out = []
        for pred in match.predictions:
            pred_out = {
                "id": pred.id,
                "match_id": pred.match_id,
                "model_id": pred.model_id,
                "model_name": pred.ai_model.name,
                "model_avatar": pred.ai_model.avatar_url,
                "result": _enumval(pred.result),
                "score_home": pred.score_home,
                "score_away": pred.score_away,
                "score_alt_home": pred.score_alt_home,
                "score_alt_away": pred.score_alt_away,
                "score_alt_prob": float(pred.score_alt_prob) if pred.score_alt_prob is not None else None,
                "confidence": pred.confidence,
                "analysis": pred.analysis,
                "is_correct_result": pred.is_correct_result,
                "is_correct_score": pred.is_correct_score,
                "created_at": pred.created_at,
            }
            preds_out.append(pred_out)

        # 构建 summary 数据
        summary_out = None
        if match.summary:
            summary_out = PredictionSummaryOut(
                id=match.summary.id,
                match_id=match.summary.match_id,
                score_home=match.summary.score_home,
                score_away=match.summary.score_away,
                score_alt_home=match.summary.score_alt_home,
                score_alt_away=match.summary.score_alt_away,
                summary=match.summary.summary,
                short_summary=match.summary.short_summary,
                confidence=match.summary.confidence,
                created_at=str(match.summary.created_at) if match.summary.created_at else None,
            )

        return MatchDetailOut(**match_dict, predictions=preds_out, summary=summary_out)

    try:
        return await get_or_set(match_detail_cache, cache_key, fetch)
    except HTTPException:
        raise
