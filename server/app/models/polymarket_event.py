from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PolymarketEvent(Base):
    """Polymarket 赛事表（一行 = 一场比赛）。

    数据来源：Polymarket Gamma API（只读拉取，只收录未来 N 天内、
    含胜负平市场的五大联赛/欧冠/欧联比赛）。
    保留联赛信息（series_id/series_name）、主客队原始名、开球时间，
    供后续与本地 matches 匹配（match_id 匹配后回填，未匹配为 NULL）。
    """

    __tablename__ = "polymarket_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pm_event_id: Mapped[Optional[str]] = mapped_column(
        String(32), comment="Polymarket 事件 id"
    )
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="Polymarket 事件 slug（唯一）"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="'主 vs 客' 标题")
    series_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Polymarket 联赛 series_id"
    )
    series_name: Mapped[Optional[str]] = mapped_column(String(100), comment="联赛名")
    home_team_raw: Mapped[Optional[str]] = mapped_column(String(150), comment="Polymarket 主队名")
    away_team_raw: Mapped[Optional[str]] = mapped_column(String(150), comment="Polymarket 客队名")
    game_start_time: Mapped[Optional[DateTime]] = mapped_column(
        DateTime, comment="开球时间（UTC）"
    )
    match_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("matches.id"), comment="关联本地比赛（后续匹配回填）"
    )
    market_count: Mapped[int] = mapped_column(Integer, default=0, comment="胜负平腿数（<=3）")
    last_synced_at: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PolymarketMarket(Base):
    """Polymarket 胜负平市场表（一行 = 一场比赛的一条腿：home/draw/away）。

    price 为该结果 'Yes' 的最新成交价（即隐含概率 0~1），
    每次同步 upsert 覆盖为最新值。
    """

    __tablename__ = "polymarket_markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("polymarket_events.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 polymarket_events.id",
    )
    pm_market_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="Polymarket 市场 id（唯一）"
    )
    condition_id: Mapped[Optional[str]] = mapped_column(String(80), comment="CLOB conditionId")
    clob_token_id_yes: Mapped[Optional[str]] = mapped_column(
        String(80), comment="CLOB token id（Yes 侧，下单用）"
    )
    clob_token_id_no: Mapped[Optional[str]] = mapped_column(
        String(80), comment="CLOB token id（No 侧）"
    )
    position_id_yes: Mapped[Optional[str]] = mapped_column(
        String(80), comment="CTF positionId（Yes 侧，查持仓用）"
    )
    position_id_no: Mapped[Optional[str]] = mapped_column(
        String(80), comment="CTF positionId（No 侧，查持仓用）"
    )
    question: Mapped[Optional[str]] = mapped_column(String(255), comment="市场问题原文")
    outcome: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="home / draw / away"
    )
    outcome_team: Mapped[Optional[str]] = mapped_column(
        String(150), comment="该腿对应的队名（draw 为 NULL）"
    )
    price: Mapped[Optional[float]] = mapped_column(Float, comment="'Yes' 最新价 = 隐含概率(0~1)")
    volume: Mapped[Optional[float]] = mapped_column(Float, comment="累计成交量(USD)")
    liquidity: Mapped[Optional[float]] = mapped_column(Float, comment="当前流动性(USD)")
    last_synced_at: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
