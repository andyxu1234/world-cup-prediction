from __future__ import annotations

import enum
from sqlalchemy import Integer, Boolean, Enum, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class VoteResult(str, enum.Enum):
    home_win = "home_win"
    draw = "draw"
    away_win = "away_win"


class UserVote(Base):
    __tablename__ = "user_votes"
    __table_args__ = (
        UniqueConstraint("user_id", "match_id", name="uk_user_match"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    result: Mapped[VoteResult] = mapped_column(Enum(VoteResult), nullable=False)
    score_home: Mapped[Optional[int]] = mapped_column(Integer)
    score_away: Mapped[Optional[int]] = mapped_column(Integer)
    is_correct_result: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_correct_score: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="votes")
    match: Mapped["Match"] = relationship("Match", back_populates="user_votes")
