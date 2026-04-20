from __future__ import annotations

from sqlalchemy import String, Integer, Boolean, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    style_tags: Mapped[Optional[dict]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # relationships
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="ai_model"
    )
