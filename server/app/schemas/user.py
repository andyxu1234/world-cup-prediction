"""用户相关 Pydantic Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel


class WechatLoginIn(BaseModel):
    code: str


class UserOut(BaseModel):
    id: int
    openid: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    total_votes: Optional[int] = 0
    correct_results: Optional[int] = 0
    correct_scores: Optional[int] = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    token: str
    user: UserOut
    profile_setup: bool = False  # 是否已完善资料（设置了非默认昵称和头像）
    is_new_user: bool = False    # 是否为新创建的用户（users 表中无记录）


class VoteIn(BaseModel):
    match_id: int
    result: str  # home_win / draw / away_win
    score_home: Optional[int] = None
    score_away: Optional[int] = None


class VoteOut(BaseModel):
    id: int
    match_id: int
    result: str
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    is_correct_result: Optional[bool] = None
    is_correct_score: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserProfileOut(BaseModel):
    user: UserOut
    vote_stats: Dict  # {total, correct_result, correct_score, result_accuracy}


class UpdateProfileIn(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
