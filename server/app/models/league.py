from __future__ import annotations

import enum
from sqlalchemy import String, Integer, DateTime, Enum, Boolean, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class LeagueType(str, enum.Enum):
    """联赛类型：常规联赛（单组积分榜）或 杯赛（多组积分榜）"""
    league = "league"
    cup = "cup"


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cn_name: Mapped[str] = mapped_column(String(50), nullable=False)
    logo: Mapped[Optional[str]] = mapped_column(String(500))
    highlightly_league_id: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[LeagueType] = mapped_column(Enum(LeagueType), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("highlightly_league_id", "season", name="uk_highlightly"),
    )

    # relationships
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="league")
    matches: Mapped[list["Match"]] = relationship("Match", back_populates="league")
