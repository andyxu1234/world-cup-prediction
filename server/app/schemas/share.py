"""分享卡片 Pydantic Schema"""

from __future__ import annotations

from typing import Optional, List, Dict
from pydantic import BaseModel


class ShareCardOut(BaseModel):
    match_id: int
    home_team: str
    home_flag: Optional[str] = None
    away_team: str
    away_flag: Optional[str] = None
    match_time: Optional[str] = None
    round: str
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    predictions: List[Dict]

    model_config = {"from_attributes": True}
