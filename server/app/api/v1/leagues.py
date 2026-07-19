"""联赛相关路由 — 多联赛改造新增"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.league import League
from app.schemas.league import LeagueOut

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("", response_model=list[LeagueOut])
async def list_leagues(
    season: int | None = Query(None, description="按赛季筛选，如 2025/2026"),
    db: AsyncSession = Depends(get_db),
):
    """返回所有联赛列表（含 is_active 状态，按 sort_order 排序）

    提供 season 参数时，仅返回该赛季的联赛行；不提供时返回全部。
    """
    stmt = select(League)
    if season is not None:
        stmt = stmt.where(League.season == season)
    stmt = stmt.order_by(League.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/seasons/available", response_model=list[int])
async def list_available_seasons(db: AsyncSession = Depends(get_db)):
    """返回数据库中已有联赛的所有 distinct 赛季，用于前端赛季切换器"""
    result = await db.execute(select(distinct(League.season)).order_by(League.season.desc()))
    return [int(s) for s in result.scalars().all() if s is not None]


@router.get("/{league_id}", response_model=LeagueOut)
async def get_league_detail(league_id: int, db: AsyncSession = Depends(get_db)):
    """返回单个联赛详情"""
    stmt = select(League).where(League.id == league_id)
    result = await db.execute(stmt)
    league = result.scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league
