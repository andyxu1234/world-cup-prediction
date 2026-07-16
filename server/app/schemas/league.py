"""联赛相关 Pydantic Schema"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class LeagueBrief(BaseModel):
    """比赛 / 预测响应中内嵌的联赛简要信息"""

    id: int
    name: str
    cn_name: str
    logo: Optional[str] = None
    type: str

    model_config = {"from_attributes": True}


class LeagueOut(BaseModel):
    """联赛完整信息"""

    id: int
    name: str
    cn_name: str
    logo: Optional[str] = None
    highlightly_league_id: int
    season: int
    type: str
    country: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

    model_config = {"from_attributes": True}
