from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel


class PlayerSeasonStatOut(BaseModel):
    """单个联赛下的球员赛季统计（用于球员详情页，可切换联赛）"""

    league_id: int
    league_name: Optional[str] = None
    season: Optional[int] = None
    team_name: Optional[str] = None
    team_cn_name: Optional[str] = None
    team_logo: Optional[str] = None
    position: Optional[str] = None
    position_cn: Optional[str] = None
    games_played: int = 0
    minutes_played: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    second_yellow: int = 0
    shots_total: int = 0
    shots_on_target: int = 0


class PlayerDetailOut(BaseModel):
    """球员详情：基础主数据 + 各联赛统计列表"""

    id: int
    name: str
    cn_name: Optional[str] = None
    full_name: Optional[str] = None
    logo: Optional[str] = None
    position_main: Optional[str] = None
    position_main_cn: Optional[str] = None
    position_secondary: Optional[str] = None
    position_secondary_cn: Optional[str] = None
    height: Optional[str] = None
    citizenship: Optional[str] = None
    birth_date: Optional[str] = None
    club: Optional[str] = None
    club_cn_name: Optional[str] = None
    stats: List[PlayerSeasonStatOut] = []
