"""联赛相关路由 — 多联赛改造新增"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.league import League
from app.schemas.league import LeagueOut

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("", response_model=list[LeagueOut])
async def list_leagues(db: AsyncSession = Depends(get_db)):
    """返回所有联赛列表（含 is_active 状态，按 sort_order 排序）"""
    stmt = select(League).order_by(League.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{league_id}", response_model=LeagueOut)
async def get_league_detail(league_id: int, db: AsyncSession = Depends(get_db)):
    """返回单个联赛详情"""
    stmt = select(League).where(League.id == league_id)
    result = await db.execute(stmt)
    league = result.scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league
