"""数据 Tab 相关接口 — 球员榜聚合

球员榜优先从 player_season_stats 表读取（由 match_player_stats 聚合快照而来）；
快照为空时回退到直接聚合 match_player_stats，保证页面始终可用。
球队榜（积分/进球/失球等）直接复用 /standings 在客户端排序，无需额外接口。
"""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models.match_player_stat import MatchPlayerStat
from app.models.data_detail import PlayerSeasonStat, Player
from app.models.team import Team
from app.schemas.player_stats import PlayerRankingsOut, PlayerRankingItem
from app.core.cache import player_rankings_cache, get_or_set

router = APIRouter(prefix="/data", tags=["data"])

VALID_TYPES = {"goals", "assists", "yellow_cards", "red_cards"}

TYPE_LABELS = {
    "goals": "射手榜",
    "assists": "助攻榜",
    "yellow_cards": "黄牌榜",
    "red_cards": "红牌榜",
}


async def _build_from_season_stats(
    db: AsyncSession, league_id: Optional[int], type: str, limit: int
) -> Optional[PlayerRankingsOut]:
    """从 player_season_stats 快照表聚合（支持跨联赛求和）"""
    metric = getattr(PlayerSeasonStat, type)
    stmt = (
        select(
            PlayerSeasonStat.player_id,
            func.max(PlayerSeasonStat.player_name).label("player_name"),
            func.max(Player.cn_name).label("player_cn_name"),
            func.max(PlayerSeasonStat.player_logo).label("player_logo"),
            func.max(Player.logo).label("db_logo"),
            func.max(PlayerSeasonStat.team_id).label("team_id"),
            func.max(PlayerSeasonStat.team_name).label("team_name"),
            func.max(PlayerSeasonStat.team_logo).label("team_logo"),
            func.coalesce(func.sum(PlayerSeasonStat.games_played), 0).label("games_played"),
            func.coalesce(func.sum(PlayerSeasonStat.minutes_played), 0).label("minutes_played"),
            func.coalesce(func.sum(PlayerSeasonStat.goals), 0).label("goals"),
            func.coalesce(func.sum(PlayerSeasonStat.assists), 0).label("assists"),
            func.coalesce(func.sum(PlayerSeasonStat.yellow_cards), 0).label("yellow_cards"),
            func.coalesce(func.sum(PlayerSeasonStat.red_cards), 0).label("red_cards"),
            func.coalesce(func.sum(PlayerSeasonStat.shots_total), 0).label("shots_total"),
            func.coalesce(func.sum(PlayerSeasonStat.shots_on_target), 0).label("shots_on_target"),
        )
        .select_from(PlayerSeasonStat)
        .outerjoin(Player, Player.id == PlayerSeasonStat.player_id)
        .group_by(PlayerSeasonStat.player_id)
    )
    if league_id is not None:
        stmt = stmt.where(PlayerSeasonStat.league_id == league_id)
    stmt = stmt.order_by(
        func.coalesce(func.sum(metric), 0).desc(),
        func.coalesce(func.sum(PlayerSeasonStat.minutes_played), 0).desc(),
    ).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return None
    team_cn_map = await _resolve_team_cn_map(db, [r.team_id for r in rows])
    return _rows_to_out(rows, league_id, type, team_cn_map)


async def _build_from_match_stats(
    db: AsyncSession, league_id: Optional[int], type: str, limit: int
) -> PlayerRankingsOut:
    """回退：直接聚合 match_player_stats（兼容未跑快照同步的情况）"""
    metric = getattr(MatchPlayerStat, type)
    stmt = (
        select(
            MatchPlayerStat.player_id,
            func.max(MatchPlayerStat.player_name).label("player_name"),
            func.max(Player.cn_name).label("player_cn_name"),
            func.max(MatchPlayerStat.player_logo).label("player_logo"),
            func.max(Player.logo).label("db_logo"),
            func.max(MatchPlayerStat.team_id).label("team_id"),
            func.max(MatchPlayerStat.team_name).label("team_name"),
            func.max(MatchPlayerStat.team_logo).label("team_logo"),
            func.count(func.distinct(MatchPlayerStat.match_id)).label("games_played"),
            func.coalesce(func.sum(MatchPlayerStat.minutes_played), 0).label("minutes_played"),
            func.coalesce(func.sum(MatchPlayerStat.goals), 0).label("goals"),
            func.coalesce(func.sum(MatchPlayerStat.assists), 0).label("assists"),
            func.coalesce(func.sum(MatchPlayerStat.yellow_cards), 0).label("yellow_cards"),
            func.coalesce(func.sum(MatchPlayerStat.red_cards), 0).label("red_cards"),
            func.coalesce(func.sum(MatchPlayerStat.shots_total), 0).label("shots_total"),
            func.coalesce(func.sum(MatchPlayerStat.shots_on_target), 0).label("shots_on_target"),
        )
        .select_from(MatchPlayerStat)
        .outerjoin(Player, Player.id == MatchPlayerStat.player_id)
        .group_by(MatchPlayerStat.player_id)
    )
    if league_id is not None:
        stmt = stmt.where(MatchPlayerStat.league_id == league_id)
    stmt = stmt.order_by(
        func.coalesce(func.sum(metric), 0).desc(),
        func.coalesce(func.sum(MatchPlayerStat.minutes_played), 0).desc(),
    ).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()
    team_cn_map = await _resolve_team_cn_map(db, [r.team_id for r in rows])
    return _rows_to_out(rows, league_id, type, team_cn_map)


async def _resolve_team_cn_map(db: AsyncSession, team_ids: list) -> dict:
    """按 Highlightly team_id 批量取球队中文名，返回 {highlightly_team_id: cn_name}

    注意：player_season_stats / match_player_stats 的 team_id 存的是 Highlightly 球队 id，
    需通过 teams.highlightly_team_id 关联，不能用本地 teams.id。
    """
    ids = {int(t) for t in team_ids if t is not None}
    if not ids:
        return {}
    stmt = select(Team.highlightly_team_id, Team.cn_name).where(Team.highlightly_team_id.in_(ids))
    rows = (await db.execute(stmt)).all()
    return {r.highlightly_team_id: r.cn_name for r in rows}


def _rows_to_out(rows, league_id: Optional[int], type: str, team_cn_map: dict) -> PlayerRankingsOut:
    items = [
        PlayerRankingItem(
            rank=rank,
            player_id=row.player_id,
            player_name=row.player_name,
            player_cn_name=row.player_cn_name,
            # 头像优先取 players 表（sofifa 头像），无则回退原始来源
            player_logo=row.db_logo or row.player_logo,
            team_id=row.team_id,
            team_name=row.team_name,
            team_cn_name=team_cn_map.get(row.team_id) if row.team_id is not None else None,
            team_logo=row.team_logo,
            games_played=row.games_played,
            minutes_played=row.minutes_played,
            goals=row.goals,
            assists=row.assists,
            yellow_cards=row.yellow_cards,
            red_cards=row.red_cards,
            shots_total=row.shots_total,
            shots_on_target=row.shots_on_target,
        )
        for rank, row in enumerate(rows, start=1)
    ]
    return PlayerRankingsOut(league_id=league_id, type=type, items=items)


@router.get("/player-rankings", response_model=PlayerRankingsOut)
async def get_player_rankings(
    league_id: Optional[int] = Query(None, description="联赛 ID（为空则返回所有联赛聚合榜）"),
    type: str = Query("goals", description="排名类型: goals/assists/yellow_cards/red_cards"),
    limit: int = Query(50, le=100, description="返回条数上限"),
    db: AsyncSession = Depends(get_db),
):
    """获取球员榜（按类型聚合排序）

    - goals: 射手榜
    - assists: 助攻榜
    - yellow_cards: 黄牌榜
    - red_cards: 红牌榜

    league_id 为空时跨所有联赛聚合（数据 Tab「全部」视图）；否则限定单个联赛。
    数据缓存 5 分钟。
    """
    if type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type, must be one of {sorted(VALID_TYPES)}")

    cache_key = f"player_rankings:{league_id}:{type}:{limit}"

    async def fetch():
        result = await _build_from_season_stats(db, league_id, type, limit)
        if result is None:
            result = await _build_from_match_stats(db, league_id, type, limit)
        return result

    return await get_or_set(player_rankings_cache, cache_key, fetch)
