"""长期预测 Pydantic Schema"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class LongTermPredictionOut(BaseModel):
    model_id: int
    model_name: Optional[str] = None
    champion: Optional[str] = None
    runner_up: Optional[str] = None
    third_place: Optional[str] = None
    analysis: Optional[str] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}
