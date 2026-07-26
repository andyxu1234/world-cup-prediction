"""Polymarket 通用市场 API

提供市场查询、筛选、同步等功能。
独立于现有的 polymarket API。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.polymarket_standalone import PolymarketStandaloneMarket
from app.services.polymarket_standalone_sync import sync_standalone_markets

router = APIRouter(prefix="/polymarket/standalone", tags=["polymarket-standalone"])


# ── 响应模型 ─────────────────────────────────────────────────────


def _market_to_dict(market: PolymarketStandaloneMarket) -> dict:
    """将市场对象转换为字典"""
    return {
        "id": market.id,
        "slug": market.slug,
        "condition_id": market.condition_id,
        "question": market.question,
        "yes_token_id": market.yes_token_id,
        "no_token_id": market.no_token_id,
        "yes_price": market.yes_price,
        "no_price": market.no_price,
        "volume": market.volume,
        "liquidity": market.liquidity,
        "min_order_size": market.min_order_size,
        "category": market.category,
        "event_slug": market.event_slug,
        "end_date": market.end_date,
        "end_ts": market.end_ts,
        "is_eligible": market.is_eligible,
        "no_entry_price": market.no_entry_price,
        "last_synced_at": market.last_synced_at.isoformat() if market.last_synced_at else None,
        "created_at": market.created_at.isoformat() if market.created_at else None,
        "updated_at": market.updated_at.isoformat() if market.updated_at else None,
    }


# ── 查询接口 ─────────────────────────────────────────────────────


@router.get("/markets")
async def get_markets(
    category: Optional[str] = Query(None, description="按类别筛选"),
    is_eligible: Optional[bool] = Query(None, description="只返回符合条件的市场"),
    max_price: Optional[float] = Query(None, description="NO 价格上限 (0-1)"),
    min_volume: Optional[float] = Query(None, description="最小成交量"),
    min_liquidity: Optional[float] = Query(None, description="最小流动性"),
    sort_by: str = Query("volume", description="排序字段: volume/liquidity/no_price/end_ts"),
    sort_order: str = Query("desc", description="排序方式: asc/desc"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """获取市场列表

    支持按类别、价格、成交量等筛选和排序。
    """
    # 构建查询
    query = select(PolymarketStandaloneMarket)

    # 筛选条件
    filters = []
    if category:
        filters.append(PolymarketStandaloneMarket.category == category)
    if is_eligible is not None:
        filters.append(PolymarketStandaloneMarket.is_eligible == is_eligible)
    if max_price is not None:
        filters.append(
            or_(
                PolymarketStandaloneMarket.no_price.is_(None),
                PolymarketStandaloneMarket.no_price <= max_price,
            )
        )
    if min_volume is not None:
        filters.append(
            or_(
                PolymarketStandaloneMarket.volume.is_(None),
                PolymarketStandaloneMarket.volume >= min_volume,
            )
        )
    if min_liquidity is not None:
        filters.append(
            or_(
                PolymarketStandaloneMarket.liquidity.is_(None),
                PolymarketStandaloneMarket.liquidity >= min_liquidity,
            )
        )

    # 只返回未过期的市场
    now_ts = datetime.now(timezone.utc).timestamp()
    filters.append(
        or_(
            PolymarketStandaloneMarket.end_ts.is_(None),
            PolymarketStandaloneMarket.end_ts > now_ts,
        )
    )

    if filters:
        query = query.where(and_(*filters))

    # 排序
    sort_column = getattr(
        PolymarketStandaloneMarket, sort_by, PolymarketStandaloneMarket.volume
    )
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 分页
    query = query.offset(offset).limit(limit)

    # 执行查询
    result = await db.execute(query)
    markets = result.scalars().all()

    # 获取总数
    count_query = select(func.count()).select_from(PolymarketStandaloneMarket)
    if filters:
        count_query = count_query.where(and_(*filters))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return {
        "markets": [_market_to_dict(m) for m in markets],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/markets/eligible")
async def get_eligible_markets(
    max_price: float = Query(0.65, description="NO 价格上限"),
    min_volume: float = Query(0, description="最小成交量"),
    sort_by: str = Query("no_price", description="排序字段"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取符合条件的市场（NO farming 候选）

    返回 NO 价格 ≤ max_price 的市场，按指定字段排序。
    """
    now_ts = datetime.now(timezone.utc).timestamp()

    query = (
        select(PolymarketStandaloneMarket)
        .where(
            and_(
                PolymarketStandaloneMarket.is_eligible == True,
                PolymarketStandaloneMarket.no_price <= max_price,
                or_(
                    PolymarketStandaloneMarket.volume.is_(None),
                    PolymarketStandaloneMarket.volume >= min_volume,
                ),
                or_(
                    PolymarketStandaloneMarket.end_ts.is_(None),
                    PolymarketStandaloneMarket.end_ts > now_ts,
                ),
            )
        )
    )

    # 排序
    sort_column = getattr(
        PolymarketStandaloneMarket, sort_by, PolymarketStandaloneMarket.no_price
    )
    query = query.order_by(sort_column.asc())

    # 分页
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    markets = result.scalars().all()

    # 获取总数
    count_query = (
        select(func.count())
        .select_from(PolymarketStandaloneMarket)
        .where(
            and_(
                PolymarketStandaloneMarket.is_eligible == True,
                PolymarketStandaloneMarket.no_price <= max_price,
                or_(
                    PolymarketStandaloneMarket.end_ts.is_(None),
                    PolymarketStandaloneMarket.end_ts > now_ts,
                ),
            )
        )
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return {
        "markets": [_market_to_dict(m) for m in markets],
        "total": total,
        "max_price": max_price,
        "limit": limit,
        "offset": offset,
    }


@router.get("/markets/{slug}")
async def get_market_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """根据 slug 获取单个市场详情"""
    result = await db.execute(
        select(PolymarketStandaloneMarket).where(
            PolymarketStandaloneMarket.slug == slug
        )
    )
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {slug}")

    return _market_to_dict(market)


@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
):
    """获取所有市场类别及其数量"""
    now_ts = datetime.now(timezone.utc).timestamp()

    result = await db.execute(
        select(
            PolymarketStandaloneMarket.category,
            func.count().label("count"),
        )
        .where(
            and_(
                PolymarketStandaloneMarket.category.isnot(None),
                PolymarketStandaloneMarket.category != "",
                or_(
                    PolymarketStandaloneMarket.end_ts.is_(None),
                    PolymarketStandaloneMarket.end_ts > now_ts,
                ),
            )
        )
        .group_by(PolymarketStandaloneMarket.category)
        .order_by(func.count().desc())
    )
    rows = result.all()

    return {
        "categories": [
            {"name": row[0], "count": row[1]}
            for row in rows
        ],
        "total_categories": len(rows),
    }


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取市场统计信息"""
    now_ts = datetime.now(timezone.utc).timestamp()

    # 总数
    total_result = await db.execute(
        select(func.count()).select_from(PolymarketStandaloneMarket)
    )
    total = total_result.scalar()

    # 未过期数
    active_result = await db.execute(
        select(func.count())
        .select_from(PolymarketStandaloneMarket)
        .where(
            or_(
                PolymarketStandaloneMarket.end_ts.is_(None),
                PolymarketStandaloneMarket.end_ts > now_ts,
            )
        )
    )
    active = active_result.scalar()

    # 符合条件数
    eligible_result = await db.execute(
        select(func.count())
        .select_from(PolymarketStandaloneMarket)
        .where(
            and_(
                PolymarketStandaloneMarket.is_eligible == True,
                or_(
                    PolymarketStandaloneMarket.end_ts.is_(None),
                    PolymarketStandaloneMarket.end_ts > now_ts,
                ),
            )
        )
    )
    eligible = eligible_result.scalar()

    # 平均 NO 价格
    avg_price_result = await db.execute(
        select(func.avg(PolymarketStandaloneMarket.no_price))
        .where(
            and_(
                PolymarketStandaloneMarket.no_price.isnot(None),
                or_(
                    PolymarketStandaloneMarket.end_ts.is_(None),
                    PolymarketStandaloneMarket.end_ts > now_ts,
                ),
            )
        )
    )
    avg_price = avg_price_result.scalar()

    # 总成交量
    volume_result = await db.execute(
        select(func.sum(PolymarketStandaloneMarket.volume))
        .where(
            or_(
                PolymarketStandaloneMarket.end_ts.is_(None),
                PolymarketStandaloneMarket.end_ts > now_ts,
            )
        )
    )
    total_volume = volume_result.scalar()

    return {
        "total_markets": total,
        "active_markets": active,
        "eligible_markets": eligible,
        "avg_no_price": round(avg_price, 4) if avg_price else None,
        "total_volume": round(total_volume, 2) if total_volume else 0,
    }


# ── 管理接口 ─────────────────────────────────────────────────────


@router.post("/sync")
async def trigger_sync():
    """手动触发市场同步

    拉取 Polymarket 活跃市场并写入数据库。
    """
    try:
        result = await sync_standalone_markets()
        return {
            "status": "ok",
            "message": "Standalone markets sync completed",
            "detail": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.post("/sync-fdv")
async def trigger_fdv_sync():
    """手动触发 FDV 事件同步

    拉取 Polymarket Events API (tag_slug=fdv) 并写入数据库。
    """
    from app.services.polymarket_fdv_sync import sync_fdv_events

    try:
        result = await sync_fdv_events()
        return {
            "status": "ok",
            "message": "FDV sync completed",
            "detail": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FDV sync failed: {e}")
