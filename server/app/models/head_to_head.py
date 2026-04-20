from __future__ import annotations

from sqlalchemy import Integer, JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class HeadToHead(Base):
    """两队历史交锋数据（最近10场）"""
    __tablename__ = "head_to_head"
    __table_args__ = (
        UniqueConstraint("team_one_id", "team_two_id", name="uk_h2h_teams"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_one_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    team_two_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    # 交锋记录 JSON 列表，格式: [{"date": "...", "homeTeam": "...", "awayTeam": "...", "score": "2-1", ...}]
    matches: Mapped[Optional[dict]] = mapped_column(JSON)
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
