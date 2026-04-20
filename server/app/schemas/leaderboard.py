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
    human: Dict
    ai_models: List[AILeaderboardItem]
    top_users: List[HumanUserRankItem] = []
    my_rank: Optional[MyRankItem] = None
