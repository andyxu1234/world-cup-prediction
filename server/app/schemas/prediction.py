"""预测相关 Pydantic Schema"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class PredictionOut(BaseModel):
    id: int
    match_id: int
    model_id: int
    model_name: Optional[str] = None
    model_avatar: Optional[str] = None
    league_id: Optional[int] = None
    result: str
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    score_alt_home: Optional[int] = None
    score_alt_away: Optional[int] = None
    score_alt_prob: Optional[Decimal] = None
    confidence: Optional[int] = None
    analysis: Optional[str] = None
    is_correct_result: Optional[bool] = None
    is_correct_score: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}
