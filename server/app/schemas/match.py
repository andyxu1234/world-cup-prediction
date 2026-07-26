"""比赛相关 Pydantic Schema"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Union
from pydantic import BaseModel, field_validator, field_serializer

from app.schemas.league import LeagueBrief


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
    league_id: Optional[int] = None
    league: Optional[LeagueBrief] = None
    summary: Optional["PredictionSummaryOut"] = None

    model_config = {"from_attributes": True}

    @field_serializer("match_time")
    def serialize_match_time(self, value: Optional[datetime]) -> Optional[str]:
        # 数据库里 match_time 按北京时间（UTC+8）存储（naive），
        # 序列化时明确标注 +08:00，避免前端/调用方误当成 UTC。
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(hours=8)))
        return value.isoformat()


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


class HomeStatsOut(BaseModel):
    """首页 Hero 区域统计数据"""
    total_matches: int = 0
    active_ai_models: int = 0
    total_predictions: int = 0
    total_users: int = 0
    total_user_predictions: int = 0
    total_leagues: int = 0



class HomeTabItem(BaseModel):
    """首页 Tab 项"""
    key: str
    label: str

    model_config = {"from_attributes": True}


class HomeTabsOut(BaseModel):
    """首页 Tab 配置"""
    tabs: List[HomeTabItem]

    model_config = {"from_attributes": True}
