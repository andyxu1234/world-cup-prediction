"""积分榜相关 Pydantic Schema"""

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel


class TeamStandingOut(BaseModel):
    """单支球队积分数据"""
    rank: int
    team_id: int
    team_name: str
    team_cn_name: Optional[str] = None
    flag_url: Optional[str] = None
    fifa_rank: Optional[int] = None
    played: int = 0
    won: int = 0
    draw: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_diff: int = 0
    points: int = 0

    model_config = {"from_attributes": True}


class GroupStandingOut(BaseModel):
    """单个小组积分榜"""
    group_name: str
    standings: List[TeamStandingOut]

    model_config = {"from_attributes": True}


class StandingsOut(BaseModel):
    """完整积分榜响应"""
    groups: List[GroupStandingOut]
    # 联赛类型：'cup'（多组）| 'league'（单组），前端据此切换积分榜布局
    type: str = "cup"

    model_config = {"from_attributes": True}


class LeagueStandingsOut(BaseModel):
    """单个联赛的积分榜（含联赛元信息）"""
    league_id: int
    league_name: str
    type: str = "cup"
    groups: List[GroupStandingOut]

    model_config = {"from_attributes": True}


class AllStandingsOut(BaseModel):
    """全部（活跃）联赛的积分榜"""
    leagues: List[LeagueStandingsOut]

    model_config = {"from_attributes": True}
