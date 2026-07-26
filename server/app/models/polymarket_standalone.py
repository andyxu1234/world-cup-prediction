"""Polymarket 通用市场表（用于 NO farming 等策略）

存储从 Polymarket Gamma API 拉取的活跃市场数据。
与 polymarket_events/polymarket_markets 独立，不关联本地比赛。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PolymarketStandaloneMarket(Base):
    """通用 Polymarket 市场表

    一行 = 一个二元 Yes/No 市场。
    数据来源：Polymarket Gamma API /markets 端点。
    用于 NO farming 等策略筛选低价 NO 市场。
    """

    __tablename__ = "polymarket_standalone_markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 市场标识
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="市场 slug（唯一标识）"
    )
    condition_id: Mapped[Optional[str]] = mapped_column(
        String(80), comment="CLOB conditionId"
    )
    question: Mapped[Optional[str]] = mapped_column(
        Text, comment="市场问题（如 'Will Bitcoin hit $200k?'）"
    )

    # Token IDs（下单用）
    yes_token_id: Mapped[Optional[str]] = mapped_column(
        String(80), comment="Yes 侧 CLOB token ID"
    )
    no_token_id: Mapped[Optional[str]] = mapped_column(
        String(80), comment="No 侧 CLOB token ID"
    )

    # 价格
    yes_price: Mapped[Optional[float]] = mapped_column(
        Float, comment="Yes 价格 (0-1)，即隐含概率"
    )
    no_price: Mapped[Optional[float]] = mapped_column(
        Float, comment="No 价格 (0-1)"
    )

    # 市场元数据
    volume: Mapped[Optional[float]] = mapped_column(
        Float, comment="累计成交量 (USD)"
    )
    liquidity: Mapped[Optional[float]] = mapped_column(
        Float, comment="当前流动性 (USD)"
    )
    min_order_size: Mapped[Optional[float]] = mapped_column(
        Float, comment="最小下单量"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(200), comment="市场类别（从 groupItemTitle 提取）"
    )
    event_slug: Mapped[Optional[str]] = mapped_column(
        String(255), comment="事件 slug"
    )

    # 时间
    end_date: Mapped[Optional[str]] = mapped_column(
        String(50), comment="结束日期（ISO 字符串）"
    )
    end_ts: Mapped[Optional[float]] = mapped_column(
        Float, comment="结束时间戳（UTC 秒，用于过期判断）"
    )

    # 策略相关
    is_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否符合 NO farming 条件（NO ≤ max_entry_price）"
    )
    no_entry_price: Mapped[Optional[float]] = mapped_column(
        Float, comment="NO 入场价格（快照）"
    )
    last_checked_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime, comment="最后检查时间"
    )

    # 同步信息
    last_synced_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime, comment="最后同步时间"
    )
    created_at: Mapped[str] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
