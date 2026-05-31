"""排行榜 Pydantic Schema"""

from __future__ import annotations

from typing import Optional, List, Dict
from pydantic import BaseModel


class AILeaderboardItem(BaseModel):
    model_id: int
    name: str
    avatar_url: Optional[str] = None
    style_tags: Optional[Dict] = None
    total: int
    correct_result: int
    result_accuracy: float
    correct_score: int
    score_accuracy: float

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class HumanUserRankItem(BaseModel):
    user_id: int
    nickname: str
    avatar_url: Optional[str] = None
    total: int
    correct_result: int
    result_accuracy: float
    correct_score: int
    score_accuracy: float
    is_me: bool = False
    real_rank: int = 0

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class MyRankItem(BaseModel):
    user_id: int
    nickname: str
    avatar_url: Optional[str] = None
    total: int
    correct_result: int
    result_accuracy: float
    correct_score: int
    score_accuracy: float
    _rank: Optional[int] = None  # 全局排名（仅前端展示用，不存DB）

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class HumanLeaderboardOut(BaseModel):
    top_users: List[HumanUserRankItem] = []
    my_rank: Optional[MyRankItem] = None


class AIDetailPredictionOut(BaseModel):
    prediction_id: int
    match_id: int
    round: str
    match_time: str | None = None
    match_status: str
    home_team_name: str
    home_team_flag: str | None = None
    away_team_name: str
    away_team_flag: str | None = None
    match_result: str | None = None
    match_home_score: int | None = None
    match_away_score: int | None = None
    predicted_result: str
    predicted_home_score: int | None = None
    predicted_away_score: int | None = None
    score_alt_home: int | None = None
    score_alt_away: int | None = None
    score_alt_prob: float | None = None
    is_correct_result: bool | None = None
    is_correct_score: bool | None = None
    confidence: float | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AIDetailOut(BaseModel):
    model_id: int
    name: str
    avatar_url: Optional[str] = None
    style_tags: Optional[Dict] = None
    total_predictions: int
    correct_results: int
    result_accuracy: float
    correct_scores: int
    score_accuracy: float
    predictions: List[AIDetailPredictionOut] = []

    model_config = {"from_attributes": True, "protected_namespaces": ()}
