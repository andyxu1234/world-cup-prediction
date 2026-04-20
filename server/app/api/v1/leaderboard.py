"""排行榜路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.schemas.leaderboard import AILeaderboardItem, HumanLeaderboardOut
from app.services.leaderboard_calc import get_ai_leaderboard, get_human_leaderboard

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/ai", response_model=List[AILeaderboardItem])
async def ai_leaderboard(
    round: str = Query("全部", description="轮次筛选"),
    sort_by: str = Query("result_accuracy", description="排序字段：result_accuracy / score_accuracy"),
    sort_order: str = Query("desc", description="排序方向：asc / desc"),
    db: AsyncSession = Depends(get_db),
):
    """AI 模型排行榜"""
    return await get_ai_leaderboard(db, round_filter=round, sort_by=sort_by, sort_order=sort_order)


@router.get("/human", response_model=HumanLeaderboardOut)
async def human_leaderboard(
    user_id: int | None = Query(None, description="当前用户ID（可选，用于返回我的排名）"),
    db: AsyncSession = Depends(get_db),
):
    """人机排行榜"""
    return await get_human_leaderboard(db, current_user_id=user_id)

