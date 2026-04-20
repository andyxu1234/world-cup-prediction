from __future__ import annotations

import enum
from decimal import Decimal
from sqlalchemy import (
    String, Integer, SmallInteger, Boolean, Text, Enum, DECIMAL,
    JSON, DateTime, ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class PredictionResult(str, enum.Enum):
    home_win = "home_win"
    draw = "draw"
    away_win = "away_win"


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("match_id", "model_id", name="uk_match_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_models.id"), nullable=False)
    result: Mapped[PredictionResult] = mapped_column(Enum(PredictionResult), nullable=False)
    score_home: Mapped[Optional[int]] = mapped_column(Integer)
    score_away: Mapped[Optional[int]] = mapped_column(Integer)
    score_alt_home: Mapped[Optional[int]] = mapped_column(Integer)
    score_alt_away: Mapped[Optional[int]] = mapped_column(Integer)
    score_alt_prob: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    confidence: Mapped[Optional[int]] = mapped_column(SmallInteger)
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON)
    is_correct_result: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_correct_score: Mapped[Optional[bool]] = mapped_column(Boolean)
    calculated_at: Mapped[Optional[str]] = mapped_column(DateTime)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
    ai_model: Mapped["AIModel"] = relationship("AIModel", back_populates="predictions")
