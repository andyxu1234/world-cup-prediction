"""Polymarket 通用市场同步服务

从 Polymarket Gamma API 拉取活跃市场，过滤后写入 polymarket_standalone_markets 表。
独立于现有的 polymarket_events/polymarket_markets 同步。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.polymarket_standalone import (
    StandaloneMarket,
    fetch_and_filter_markets,
    DEFAULT_MAX_END_DATE_MONTHS,
)
from app.database import async_session_factory
from app.models.polymarket_standalone import PolymarketStandaloneMarket


def _utcnow_naive() -> datetime:
    """返回当前 UTC 时间（无时区）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts_to_naive_utc(ts: float) -> Optional[datetime]:
    """时间戳转 naive UTC datetime"""
    if not ts or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


async def _upsert_market(
    session: AsyncSession,
    market: StandaloneMarket,
    now: datetime,
    max_entry_price: float,
) -> bool:
    """按 slug upsert 一个市场，返回是否新建"""
    row = (
        await session.execute(
            select(PolymarketStandaloneMarket).where(
                PolymarketStandaloneMarket.slug == market.slug
            )
        )
    ).scalar_one_or_none()

    is_new = row is None
    if row is None:
        row = PolymarketStandaloneMarket(slug=market.slug)
        session.add(row)

    # 更新字段
    row.condition_id = market.condition_id or None
    row.question = market.question or None
    row.yes_token_id = market.yes_token_id or None
    row.no_token_id = market.no_token_id or None
    row.yes_price = market.yes_price
    row.no_price = market.no_price
    row.volume = market.volume
    row.liquidity = market.liquidity
    row.min_order_size = market.min_order_size
    row.category = market.category or None
    row.event_slug = market.event_slug or None
    row.end_date = market.end_date or None
    row.end_ts = market.end_ts if market.end_ts > 0 else None
    row.last_synced_at = now

    # 判断是否符合 NO farming 条件
    if market.no_price and market.no_price <= max_entry_price:
        row.is_eligible = True
        row.no_entry_price = market.no_price
    else:
        row.is_eligible = False
        row.no_entry_price = None

    return is_new


async def sync_standalone_markets() -> dict:
    """同步 Polymarket 通用市场

    拉取所有活跃市场，过滤后写入 polymarket_standalone_markets 表。
    清除已过期的市场（end_ts < now）。

    Returns:
        {
            "total_fetched": int,
            "total_filtered": int,
            "new_markets": int,
            "updated_markets": int,
            "expired_removed": int,
            "eligible_count": int,
        }
    """
    settings = get_settings()
    max_entry_price = getattr(settings, "POLYMARKET_MAX_ENTRY_PRICE", 0.65)
    max_end_date_months = getattr(settings, "POLYMARKET_MAX_END_DATE_MONTHS", DEFAULT_MAX_END_DATE_MONTHS)

    logger.info("[Standalone] 开始同步 Polymarket 通用市场...")

    # 拉取并过滤市场
    try:
        markets = await fetch_and_filter_markets(
            max_end_date_months=max_end_date_months,
        )
    except Exception as e:
        logger.error(f"[Standalone] 拉取市场失败: {e}")
        raise

    logger.info(f"[Standalone] 拉取完成: {len(markets)} 个候选市场")

    # 写入数据库
    now = _utcnow_naive()
    new_count = 0
    updated_count = 0
    eligible_count = 0

    async with async_session_factory() as session:
        for market in markets:
            is_new = await _upsert_market(session, market, now, max_entry_price)
            if is_new:
                new_count += 1
            else:
                updated_count += 1
            if market.no_price and market.no_price <= max_entry_price:
                eligible_count += 1

        # 清除已过期的市场（end_ts < now - 2h）
        now_ts = datetime.now(timezone.utc).timestamp()
        cutoff_ts = now_ts - 2 * 3600  # 容忍 2 小时
        expired_result = await session.execute(
            delete(PolymarketStandaloneMarket).where(
                PolymarketStandaloneMarket.end_ts.isnot(None),
                PolymarketStandaloneMarket.end_ts < cutoff_ts,
            )
        )
        expired_removed = expired_result.rowcount

        await session.commit()

    logger.info(
        f"[Standalone] 同步完成: "
        f"{new_count} 新建, {updated_count} 更新, "
        f"{expired_removed} 过期移除, "
        f"{eligible_count} 符合条件 (NO ≤ {max_entry_price})"
    )

    return {
        "total_fetched": len(markets),
        "total_filtered": len(markets),
        "new_markets": new_count,
        "updated_markets": updated_count,
        "expired_removed": expired_removed,
        "eligible_count": eligible_count,
    }
