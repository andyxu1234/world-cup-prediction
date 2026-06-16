"""小组积分榜路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.standings import StandingsOut
from app.services.standings_calc import calculate_standings
from app.core.cache import standings_cache, get_or_set

router = APIRouter(prefix="/standings", tags=["standings"])


@router.get("", response_model=StandingsOut)
async def get_standings(db: AsyncSession = Depends(get_db)):
    """获取世界杯小组赛积分榜

    从已结束的小组赛比赛结果中计算各小组的积分排名。
    数据缓存 5 分钟。
    """
    return await get_or_set(standings_cache, "all_standings", lambda: calculate_standings(db))
