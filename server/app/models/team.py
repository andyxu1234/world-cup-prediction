from __future__ import annotations

from sqlalchemy import String, Integer, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cn_name: Mapped[Optional[str]] = mapped_column(String(50))
    flag_url: Mapped[Optional[str]] = mapped_column(String(500))
    group_name: Mapped[Optional[str]] = mapped_column(String(10))
    fifa_rank: Mapped[Optional[int]] = mapped_column(Integer)
    highlightly_team_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    # 球队赛季统计（JSON，来自 /teams/statistics/{id}）
    season_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    # 最近5场状态（JSON，来自 /last-five-games）
    recent_form: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    home_matches: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.home_team_id", back_populates="home_team"
    )
    away_matches: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.away_team_id", back_populates="away_team"
    )
