from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    Date,
    Boolean,
    Enum,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OddsType(str, enum.Enum):
    """赔率类型：赛前 / 滚球"""

    prematch = "prematch"
    live = "live"


class Bookmaker(Base):
    """博彩公司字典表

    仅保留参与赔率拉取的博彩公司（is_active=True），种子数据见 Alembic 迁移。
    highlightly_bookmaker_id 对应 Highlightly API 的 bookmakerId。
    """

    __tablename__ = "bookmakers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    highlightly_bookmaker_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, comment="Highlightly 博彩公司 ID"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="博彩公司名称")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1", comment="是否参与赔率拉取"
    )

    # relationships
    odds: Mapped[list["MatchOdd"]] = relationship("MatchOdd", back_populates="bookmaker")


class MatchOdd(Base):
    """比赛赔率明细表（追加式快照，支持日内/逐日赔率走势）

    颗粒度：比赛 → 博彩公司 → 市场(market) → 选项(value)
           → 快照日期(snapshot_date) → 快照小时桶(snapshot_hour) → odd 数值。
    按 (match_id, bookmaker_id, odds_type, market, value, snapshot_date, snapshot_hour) 唯一：
    - 同一小时桶内多次拉取 → upsert 覆盖该小时最新值（幂等）。
    - 跨小时桶（如每 6 小时跑一次）→ 追加新的一行快照，累积出日内赔率走势。
    - 跨天 → 自然追加，累积逐日走势。
    snapshot_hour 为 0-23 的小时桶，每小时一个赔率点，可支持任意同步频率。
    """

    __tablename__ = "match_odds"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "bookmaker_id",
            "odds_type",
            "market",
            "value",
            "snapshot_date",
            "snapshot_hour",
            name="uk_match_odds",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id"), nullable=False, index=True, comment="关联比赛"
    )
    bookmaker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookmakers.highlightly_bookmaker_id"), nullable=False, index=True,
        comment="Highlightly bookmakerId（关联 bookmakers.highlightly_bookmaker_id，冗余便于直接筛）"
    )
    bookmaker_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="博彩公司名称")
    odds_type: Mapped[OddsType] = mapped_column(
        Enum(OddsType), default=OddsType.prematch, nullable=False, comment="prematch / live"
    )
    market: Mapped[str] = mapped_column(String(80), nullable=False, comment="市场，如 Full Time Result / Asian Handicap +0.25/-0.25")
    value: Mapped[str] = mapped_column(String(50), nullable=False, comment="选项，如 Home / Over / 2 : 0")
    odd: Mapped[float] = mapped_column(Float, nullable=False, comment="赔率数值")
    snapshot_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True, comment="快照日期（用于按天聚合走势）"
    )
    snapshot_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="快照小时桶(0-23)，每小时一个赔率点，用于日内走势",
    )
    fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="抓取时间（精确时刻）"
    )

    # relationships
    match: Mapped["Match"] = relationship("Match", back_populates="match_odds")
    bookmaker: Mapped["Bookmaker"] = relationship("Bookmaker", back_populates="odds")
