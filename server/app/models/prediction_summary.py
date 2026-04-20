from __future__ import annotations

from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, func, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.database import Base


class PredictionSummary(Base):
    __tablename__ = "prediction_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    # 综合预测比分
    score_home: Mapped[Optional[int]] = mapped_column(Integer)
    score_away: Mapped[Optional[int]] = mapped_column(Integer)
    # 备选预测比分
    score_alt_home: Mapped[Optional[int]] = mapped_column(Integer)
    score_alt_away: Mapped[Optional[int]] = mapped_column(Integer)
    # AI 综合分析总结（结合所有AI的分析生成的总体结论）
    summary: Mapped[Optional[str]] = mapped_column(Text)
    # AI 共识（简短结论，用于首页展示）
    short_summary: Mapped[Optional[str]] = mapped_column(String(100))
    # 综合信心指数 (1-10)
    confidence: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    match: Mapped["Match"] = relationship("Match", back_populates="summary")
