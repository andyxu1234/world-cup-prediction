"""比赛相关 Pydantic Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, field_validator


# --- Team ---
class TeamOut(BaseModel):
    id: int
    name: str
    cn_name: Optional[str] = None
    flag_url: Optional[str] = None
    group_name: Optional[str] = None
    fifa_rank: Optional[int] = None

    model_config = {"from_attributes": True}


# --- Match ---
class MatchListOut(BaseModel):
    id: int
    match_day: int
    round: str
    match_time: Optional[datetime] = None
    venue: Optional[str] = None
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    result: Optional[str] = None
    home_team: TeamOut
    away_team: TeamOut
    summary: Optional["PredictionSummaryOut"] = None

    model_config = {"from_attributes": True}


class MatchDetailOut(MatchListOut):
    """比赛详情，包含 AI 预测"""
    predictions: List[dict] = []
    summary: Optional["PredictionSummaryOut"] = None

    model_config = {"from_attributes": True}


class PredictionSummaryOut(BaseModel):
    """AI 预测总结"""
    id: int
    match_id: int
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    score_alt_home: Optional[int] = None
    score_alt_away: Optional[int] = None
    summary: Optional[str] = None
    short_summary: Optional[str] = None
    confidence: Optional[int] = None
    created_at: Optional[Union[datetime, str]] = None

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class MatchQuery(BaseModel):
    round: Optional[str] = None
    status: Optional[str] = None
