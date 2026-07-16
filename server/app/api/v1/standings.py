"""小组积分榜路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.standings import StandingsOut
from app.services.standings_calc import calculate_standings
from app.core.cache import standings_cache, get_or_set

router = APIRouter(prefix="/standings", tags=["standings"])


@router.get("", response_model=StandingsOut)
async def get_standings(
    league_id: int = Query(..., description="联赛 ID（必填，世界杯=1，英超=2，…）"),
    db: AsyncSession = Depends(get_db),
):
    """获取指定联赛的积分榜

    - 常规联赛（type=league）：单组积分榜（如英超 20 队排名）
    - 杯赛（type=cup）：多组积分榜（如世界杯 8 组 / 欧冠 8 组）

    数据缓存 5 分钟。
    """
    cache_key = f"standings:{league_id}"
    try:
        return await get_or_set(standings_cache, cache_key, lambda: calculate_standings(db, league_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
