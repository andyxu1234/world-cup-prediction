"""球队详情路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.team import Team
from app.schemas.team_detail import TeamDetailOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_id}", response_model=TeamDetailOut)
async def get_team_detail(team_id: int, db: AsyncSession = Depends(get_db)):
    """获取球队详情：基础信息 + 赛季统计(season_stats) + 近期状态(recent_form)"""
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamDetailOut(
        id=team.id,
        name=team.name,
        cn_name=team.cn_name,
        flag_url=team.flag_url,
        group_name=team.group_name,
        fifa_rank=team.fifa_rank,
        season_stats=team.season_stats,
        recent_form=team.recent_form,
    )
