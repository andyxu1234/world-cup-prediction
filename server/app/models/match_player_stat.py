from __future__ import annotations

from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class MatchPlayerStat(Base):
    """单场比赛逐球员的盒子分数据（来自 Highlightly /box-score/{matchId}）

    以 (match_id, player_id) 为唯一键，每次同步某场比赛时整场重算（幂等 upsert）。
    球员榜通过按 league_id + player_id 聚合该表得到。
    """

    __tablename__ = "match_player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    # 冗余 league_id，避免排名查询时再 JOIN matches
    league_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_name: Mapped[str] = mapped_column(String(120), nullable=False)
    player_logo: Mapped[Optional[str]] = mapped_column(String(500))
    team_id: Mapped[Optional[int]] = mapped_column(Integer)
    team_name: Mapped[Optional[str]] = mapped_column(String(120))
    team_logo: Mapped[Optional[str]] = mapped_column(String(500))
    position: Mapped[Optional[str]] = mapped_column(String(30))
    shirt_number: Mapped[Optional[int]] = mapped_column(Integer)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    is_substitute: Mapped[bool] = mapped_column(Boolean, default=False)
    minutes_played: Mapped[int] = mapped_column(Integer, default=0)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, default=0)
    second_yellow: Mapped[int] = mapped_column(Integer, default=0)
    shots_total: Mapped[int] = mapped_column(Integer, default=0)
    shots_on_target: Mapped[int] = mapped_column(Integer, default=0)
    shots_off_target: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uk_match_player"),
    )
