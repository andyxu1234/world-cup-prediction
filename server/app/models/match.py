from __future__ import annotations

import enum
from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class MatchStatus(str, enum.Enum):
    upcoming = "upcoming"
    live = "live"
    finished = "finished"


class MatchResult(str, enum.Enum):
    home_win = "home_win"
    draw = "draw"
    away_win = "away_win"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_day: Mapped[int] = mapped_column(Integer, nullable=False)
    round: Mapped[str] = mapped_column(String(50), nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    match_time: Mapped[str] = mapped_column(DateTime, nullable=False)
    venue: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus), default=MatchStatus.upcoming
    )
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    result: Mapped[Optional[MatchResult]] = mapped_column(Enum(MatchResult))
    highlightly_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    home_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[home_team_id], back_populates="home_matches"
    )
    away_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[away_team_id], back_populates="away_matches"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="match"
    )
    user_votes: Mapped[list["UserVote"]] = relationship(
        "UserVote", back_populates="match"
    )
    summary: Mapped[Optional["PredictionSummary"]] = relationship(
        "PredictionSummary", back_populates="match", uselist=False
    )
