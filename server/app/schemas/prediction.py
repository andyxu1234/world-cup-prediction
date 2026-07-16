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


class FaceSlapOut(BaseModel):
    """打脸条目"""
    prediction_id: int
    model_name: str
    model_avatar: Optional[str] = None
    match_id: int
    league_id: Optional[int] = None
    league_name: Optional[str] = None
    home_team: str          # 主队中文名
    away_team: str          # 客队中文名
    home_team_flag: Optional[str] = None   # 主队国旗
    away_team_flag: Optional[str] = None   # 客队国旗
    predicted_result: str
    predicted_score: str
    actual_result: str
    actual_score: str
    confidence: Optional[int] = None
    analysis: Optional[str] = None
    face_slap_index: float = 0
    score_absurdity: int = 0  # 比分离谱度：|预测主-实际主| + |预测客-实际客|
    match_time: Optional[str] = None  # 比赛时间

    model_config = {"from_attributes": True, "protected_namespaces": ()}
