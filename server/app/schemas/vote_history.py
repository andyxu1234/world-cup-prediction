"""投票历史 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VoteHistoryItem(BaseModel):
    id: int
    match_id: int
    league_name: Optional[str] = None
    round: str
    match_time: Optional[str] = None
    home_team_name: str
    away_team_name: str
    home_team_flag: Optional[str] = None
    away_team_flag: Optional[str] = None
    match_status: str  # upcoming / live / finished
    match_result: Optional[str] = None  # home_win / draw / away_win
    match_home_score: Optional[int] = None
    match_away_score: Optional[int] = None
    predicted_result: str
    predicted_home_score: Optional[int] = None
    predicted_away_score: Optional[int] = None
    is_correct_result: Optional[bool] = None
    is_correct_score: Optional[bool] = None
    created_at: Optional[str] = None
