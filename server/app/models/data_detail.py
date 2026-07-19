from __future__ import annotations

from sqlalchemy import String, Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class LeagueStanding(Base):
    """积分榜/球队榜统一数据源（来自 Highlightly /standings 同步落地）

    按 (league_id, season, group_name, highlightly_team_id) 唯一；
    球队榜直接复用同一张表，按不同指标排序即可。
    """

    __tablename__ = "league_standings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    group_name: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    highlightly_team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    team_name: Mapped[Optional[str]] = mapped_column(String(120))
    team_logo: Mapped[Optional[str]] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[int] = mapped_column(Integer, default=0)
    won: Mapped[int] = mapped_column(Integer, default=0)
    draw: Mapped[int] = mapped_column(Integer, default=0)
    lost: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    goal_diff: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    # 主客场拆分（丰富球队榜）
    home_won: Mapped[int] = mapped_column(Integer, default=0)
    home_draw: Mapped[int] = mapped_column(Integer, default=0)
    home_lost: Mapped[int] = mapped_column(Integer, default=0)
    home_gf: Mapped[int] = mapped_column(Integer, default=0)
    home_ga: Mapped[int] = mapped_column(Integer, default=0)
    away_won: Mapped[int] = mapped_column(Integer, default=0)
    away_draw: Mapped[int] = mapped_column(Integer, default=0)
    away_lost: Mapped[int] = mapped_column(Integer, default=0)
    away_gf: Mapped[int] = mapped_column(Integer, default=0)
    away_ga: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "league_id", "season", "group_name", "highlightly_team_id",
            name="uk_league_standing",
        ),
    )


class Player(Base):
    """球员主数据（来自 Highlightly /players/{id}）

    id = Highlightly player id（天然主键）。
    基础字段（name/logo/position）由 box-score 同步时廉价写入；
    丰富字段（height/citizenship/birth_date/club）在打开球员详情页时按需补充。
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    cn_name: Mapped[Optional[str]] = mapped_column(String(120))
    full_name: Mapped[Optional[str]] = mapped_column(String(120))
    logo: Mapped[Optional[str]] = mapped_column(String(500))
    position_main: Mapped[Optional[str]] = mapped_column(String(60))
    position_secondary: Mapped[Optional[str]] = mapped_column(String(120))
    height: Mapped[Optional[str]] = mapped_column(String(20))
    citizenship: Mapped[Optional[str]] = mapped_column(String(60))
    birth_date: Mapped[Optional[str]] = mapped_column(String(40))
    club: Mapped[Optional[str]] = mapped_column(String(120))
    fetched_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class PlayerSeasonStat(Base):
    """球员榜聚合快照（由 match_player_stats 按联赛聚合而来）

    按 (league_id, season, player_id) 唯一；每次同步整联赛重建（幂等）。
    """

    __tablename__ = "player_season_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    player_name: Mapped[str] = mapped_column(String(120), nullable=False)
    player_logo: Mapped[Optional[str]] = mapped_column(String(500))
    # 主力球队：该球员在本联赛出场场次最多的球队（转会场景取多数方）。
    # 注意：此处 team_id 与 match_player_stats.team_id 一致，存的是 Highlightly 球队 id，
    # 需用 teams.highlightly_team_id 关联才能拿到 cn_name（与本地 teams.id 不是同一套）。
    team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    team_name: Mapped[Optional[str]] = mapped_column(String(120))
    team_logo: Mapped[Optional[str]] = mapped_column(String(500))
    position: Mapped[Optional[str]] = mapped_column(String(30))
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    minutes_played: Mapped[int] = mapped_column(Integer, default=0)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, default=0)
    second_yellow: Mapped[int] = mapped_column(Integer, default=0)
    shots_total: Mapped[int] = mapped_column(Integer, default=0)
    shots_on_target: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("league_id", "season", "player_id", name="uk_player_season"),
    )
