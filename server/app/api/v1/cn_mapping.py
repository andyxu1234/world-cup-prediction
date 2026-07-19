"""通用中英文映射路由 — 返回全部（或按 category 过滤）的中英文对照，供前端展示使用"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cn_mapping import CnMapping
from app.schemas.cn_mapping import CnMappingOut

router = APIRouter(prefix="/cn-mappings", tags=["cn-mappings"])


@router.get("", response_model=list[CnMappingOut])
async def list_cn_mappings(
    category: Optional[str] = Query(None, description="映射类别，如 round / position；为空返回全部"),
    db: AsyncSession = Depends(get_db),
):
    """返回通用中英文映射（可按 category 过滤）"""
    stmt = select(CnMapping)
    if category:
        stmt = stmt.where(CnMapping.category == category)
    stmt = stmt.order_by(CnMapping.category, CnMapping.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
