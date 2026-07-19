"""排行榜路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.schemas.leaderboard import AILeaderboardItem, HumanLeaderboardOut, AIDetailOut
from app.services.leaderboard_calc import get_ai_leaderboard, get_human_leaderboard, get_ai_model_detail

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/ai", response_model=List[AILeaderboardItem])
async def ai_leaderboard(
    sort_by: str = Query("result_accuracy", description="排序字段：result_accuracy / score_accuracy"),
    sort_order: str = Query("desc", description="排序方向：asc / desc"),
    league_ids: List[int] = Query([], description="联赛筛选，可传多个 league_ids=1&league_ids=2；不传返回全局排行"),
    db: AsyncSession = Depends(get_db),
):
    """AI 模型排行榜"""
    return await get_ai_leaderboard(db, sort_by=sort_by, sort_order=sort_order, league_ids=league_ids)


@router.get("/human", response_model=HumanLeaderboardOut)
async def human_leaderboard(
    user_id: int | None = Query(None, description="当前用户ID（可选，用于返回我的排名）"),
    league_ids: List[int] = Query([], description="联赛筛选，可传多个 league_ids=1&league_ids=2；不传返回全局排行"),
    db: AsyncSession = Depends(get_db),
):
    """人机排行榜"""
    return await get_human_leaderboard(db, current_user_id=user_id, league_ids=league_ids)


@router.get("/ai/{model_id}", response_model=AIDetailOut)
async def ai_model_detail(
    model_id: int,
    league_ids: List[int] = Query([], description="联赛筛选，只统计这些联赛的预测；不传返回全部联赛"),
    db: AsyncSession = Depends(get_db),
):
    """AI 模型预测详情"""
    return await get_ai_model_detail(db, model_id=model_id, league_ids=league_ids)

