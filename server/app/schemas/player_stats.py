from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PlayerRankingItem(BaseModel):
    """球员榜单项（按联赛聚合后的结果）"""

    rank: int
    player_id: int
    player_name: str
    player_cn_name: Optional[str] = None
    player_logo: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    team_cn_name: Optional[str] = None
    team_logo: Optional[str] = None
    games_played: int = 0
    minutes_played: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    shots_total: int = 0
    shots_on_target: int = 0

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class PlayerRankingsOut(BaseModel):
    """球员榜返回结构"""

    league_id: int
    type: str
    items: List[PlayerRankingItem]
