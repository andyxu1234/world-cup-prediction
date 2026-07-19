from __future__ import annotations

from typing import Optional, Any

from pydantic import BaseModel


class TeamDetailOut(BaseModel):
    """球队详情：基础信息 + 赛季统计 + 近期状态"""

    id: int
    name: str
    cn_name: Optional[str] = None
    flag_url: Optional[str] = None
    group_name: Optional[str] = None
    fifa_rank: Optional[int] = None
    # 来自 /teams/statistics/{id} 的 JSON（按联赛拆分胜平负/进失球/主客场）
    season_stats: Optional[Any] = None
    # 来自 /last-five-games 的 JSON（最近 5 场战绩）
    recent_form: Optional[Any] = None

    model_config = {"from_attributes": True}
