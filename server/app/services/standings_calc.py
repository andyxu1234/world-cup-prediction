"""小组积分榜计算服务

从 matches 表查询已结束的小组赛，计算每支球队的积分、净胜球等数据。
"""

from __future__ import annotations

from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.match import Match, MatchStatus, MatchResult
from app.models.team import Team
from app.schemas.standings import TeamStandingOut, GroupStandingOut, StandingsOut


async def calculate_standings(db: AsyncSession, league_id: int) -> StandingsOut:
    """计算指定联赛的积分榜

    逻辑：
    - 杯赛（type=cup）：查询已结束的小组赛（round 包含 'Group Stage'），按 group_name 分组
    - 常规联赛（type=league）：查询该联赛所有已结束比赛，单组积分榜（以联赛中文名为组名）

    Args:
        db: 数据库会话
        league_id: 联赛主键 ID

    Raises:
        ValueError: 联赛不存在
    """
    from app.models.league import League

    # 查询联赛信息，决定积分榜结构
    league_stmt = select(League).where(League.id == league_id)
    league = (await db.execute(league_stmt)).scalar_one_or_none()
    if league is None:
        raise ValueError(f"League {league_id} not found")

    is_cup = (league.type.value == "cup") if hasattr(league.type, "value") else (league.type == "cup")

    # 查询已结束比赛，并加载关联的球队数据
    conditions = [
        Match.status == MatchStatus.finished,
        Match.league_id == league_id,
    ]
    if is_cup:
        # 杯赛只统计小组赛阶段
        conditions.append(Match.round.contains("Group Stage"))

    stmt = (
        select(Match)
        .where(*conditions)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
        )
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()

    # 用字典收集每支球队的统计数据
    # key: (group_name, team_id) -> stats dict
    team_stats: dict[tuple[str, int], dict] = {}

    def group_key(team: Team) -> str:
        """单组联赛用联赛中文名作为组名；杯赛用球队的 group_name"""
        if is_cup:
            return team.group_name or "未知组"
        return league.cn_name

    def get_or_init(team: Team) -> dict:
        """获取或初始化球队统计数据"""
        key = (group_key(team), team.id)
        if key not in team_stats:
            team_stats[key] = {
                "team_id": team.id,
                "team_name": team.name,
                "team_cn_name": team.cn_name,
                "flag_url": team.flag_url,
                "fifa_rank": team.fifa_rank,
                "group_name": group_key(team),
                "played": 0,
                "won": 0,
                "draw": 0,
                "lost": 0,
                "goals_for": 0,
                "goals_against": 0,
            }
        return team_stats[key]

    # 遍历比赛，累计数据
    for match in matches:
        home = get_or_init(match.home_team)
        away = get_or_init(match.away_team)

        # 更新场次
        home["played"] += 1
        away["played"] += 1

        # 更新进球数
        home_score = match.home_score or 0
        away_score = match.away_score or 0
        home["goals_for"] += home_score
        home["goals_against"] += away_score
        away["goals_for"] += away_score
        away["goals_against"] += home_score

        # 更新胜负平
        if match.result == MatchResult.home_win:
            home["won"] += 1
            away["lost"] += 1
        elif match.result == MatchResult.away_win:
            away["won"] += 1
            home["lost"] += 1
        elif match.result == MatchResult.draw:
            home["draw"] += 1
            away["draw"] += 1

    # 按小组分组
    groups: dict[str, list[dict]] = defaultdict(list)
    for (group_name, _), stats in team_stats.items():
        groups[group_name].append(stats)

    # 计算积分、净胜球并排序
    result_groups: list[GroupStandingOut] = []
    for group_name in sorted(groups.keys()):
        teams = groups[group_name]

        # 计算积分和净胜球
        for t in teams:
            t["points"] = t["won"] * 3 + t["draw"]
            t["goal_diff"] = t["goals_for"] - t["goals_against"]

        # 排序：积分 > 净胜球 > 进球数 > 队伍ID（稳定排序）
        teams.sort(
            key=lambda x: (-x["points"], -x["goal_diff"], -x["goals_for"], x["team_id"])
        )

        # 构建排名列表
        standings = []
        for rank, t in enumerate(teams, start=1):
            standings.append(TeamStandingOut(
                rank=rank,
                team_id=t["team_id"],
                team_name=t["team_name"],
                team_cn_name=t["team_cn_name"],
                flag_url=t["flag_url"],
                fifa_rank=t["fifa_rank"],
                played=t["played"],
                won=t["won"],
                draw=t["draw"],
                lost=t["lost"],
                goals_for=t["goals_for"],
                goals_against=t["goals_against"],
                goal_diff=t["goal_diff"],
                points=t["points"],
            ))

        result_groups.append(GroupStandingOut(
            group_name=group_name,
            standings=standings,
        ))

    return StandingsOut(groups=result_groups, type="cup" if is_cup else "league")
