from __future__ import annotations

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class LongTermPrediction(Base):
    __tablename__ = "long_term_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_models.id"), nullable=False)
    champion_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    runner_up_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    third_place_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    league_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leagues.id"))
    league: Mapped[Optional["League"]] = relationship("League", back_populates="long_term_predictions")

    ai_model: Mapped["AIModel"] = relationship("AIModel")
    champion_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[champion_team_id])
    runner_up_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[runner_up_team_id])
    third_place_team: Mapped[Optional["Team"]] = relationship("Team", foreign_keys=[third_place_team_id])
