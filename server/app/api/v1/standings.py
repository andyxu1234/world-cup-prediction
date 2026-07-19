"""小组积分榜路由

积分榜/球队榜统一读取 league_standings 表（来自 Highlightly /standings 同步落地）。
表为空时回退到本地 matches 现算（calculate_standings），保证页面不报错。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from app.database import get_db
from app.schemas.standings import (
    StandingsOut,
    AllStandingsOut,
    TeamStandingOut,
    GroupStandingOut,
    LeagueStandingsOut,
)
from app.services.standings_calc import calculate_standings
from app.core.cache import standings_cache, get_or_set
from app.models.data_detail import LeagueStanding
from app.models.league import League, LeagueType
from app.models.team import Team

router = APIRouter(prefix="/standings", tags=["standings"])


async def _build_standings_out(db: AsyncSession, league: League, rows: list[LeagueStanding]) -> StandingsOut:
    """根据 league_standings 行构建响应；为空则回退到现算"""
    if not rows:
        return await calculate_standings(db, league.id)

    team_ids = [r.team_id for r in rows if r.team_id]
    hl_team_ids = [r.highlightly_team_id for r in rows if r.highlightly_team_id]
    team_map: dict[int, Team] = {}
    hl_team_map: dict[int, Team] = {}
    if team_ids or hl_team_ids:
        trows = (
            await db.execute(
                select(Team).where(
                    (Team.id.in_(team_ids)) | (Team.highlightly_team_id.in_(hl_team_ids))
                )
            )
        ).scalars().all()
        team_map = {t.id: t for t in trows}
        hl_team_map = {t.highlightly_team_id: t for t in trows if t.highlightly_team_id}

    is_cup = league.type == LeagueType.cup
    groups_dict: dict[str, list[TeamStandingOut]] = defaultdict(list)
    for r in rows:
        team = None
        if r.team_id:
            team = team_map.get(r.team_id)
        if team is None and r.highlightly_team_id:
            team = hl_team_map.get(r.highlightly_team_id)
        item = TeamStandingOut(
            rank=r.position,
            team_id=team.id if team else (r.team_id or 0),
            team_name=team.name if team else (r.team_name or "未知球队"),
            team_cn_name=team.cn_name if team else None,
            flag_url=team.flag_url if team else r.team_logo,
            fifa_rank=team.fifa_rank if team else None,
            played=r.played,
            won=r.won,
            draw=r.draw,
            lost=r.lost,
            goals_for=r.goals_for,
            goals_against=r.goals_against,
            goal_diff=r.goal_diff,
            points=r.points,
        )
        gname = r.group_name if is_cup else (league.cn_name or league.name)
        groups_dict[gname].append(item)

    groups: list[GroupStandingOut] = []
    for gname in sorted(groups_dict.keys()):
        groups.append(GroupStandingOut(group_name=gname, standings=groups_dict[gname]))
    return StandingsOut(groups=groups, type="cup" if is_cup else "league")


async def _get_standings_for(db: AsyncSession, league_id: int) -> StandingsOut:
    league = (await db.execute(select(League).where(League.id == league_id))).scalar_one_or_none()
    if league is None:
        raise ValueError(f"League {league_id} not found")
    rows = (
        await db.execute(
            select(LeagueStanding)
            .where(LeagueStanding.league_id == league_id)
            .order_by(LeagueStanding.group_name, LeagueStanding.position)
        )
    ).scalars().all()
    return await _build_standings_out(db, league, rows)


@router.get("", response_model=StandingsOut)
async def get_standings(
    league_id: int = Query(..., description="联赛 ID（必填，世界杯=1，英超=2，…）"),
    db: AsyncSession = Depends(get_db),
):
    """获取指定联赛的积分榜（数据来自 league_standings 表，空则回退现算）"""
    cache_key = f"standings:{league_id}"
    try:
        return await get_or_set(standings_cache, cache_key, lambda: _get_standings_for(db, league_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


async def _get_all_standings(db: AsyncSession) -> AllStandingsOut:
    leagues = (
        await db.execute(
            select(League).where(League.is_active == True).order_by(League.sort_order, League.id)  # noqa: E712
        )
    ).scalars().all()

    out: list[LeagueStandingsOut] = []
    for lg in leagues:
        rows = (
            await db.execute(
                select(LeagueStanding)
                .where(LeagueStanding.league_id == lg.id)
                .order_by(LeagueStanding.group_name, LeagueStanding.position)
            )
        ).scalars().all()
        st = await _build_standings_out(db, lg, rows)
        if not st.groups or all(len(g.standings) == 0 for g in st.groups):
            continue
        out.append(
            LeagueStandingsOut(
                league_id=lg.id,
                league_name=lg.cn_name or lg.name,
                type=st.type,
                groups=st.groups,
            )
        )
    return AllStandingsOut(leagues=out)


@router.get("/all", response_model=AllStandingsOut)
async def get_all_standings(db: AsyncSession = Depends(get_db)):
    """获取所有活跃联赛的积分榜（数据 Tab 使用，不按用户选择过滤）"""
    return await get_or_set(standings_cache, "all", lambda: _get_all_standings(db))
