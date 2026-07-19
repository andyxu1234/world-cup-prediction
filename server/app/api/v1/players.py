"""球员详情路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models.cn_mapping import CnMapping
from app.models.data_detail import Player, PlayerSeasonStat
from app.models.league import League
from app.models.team import Team
from app.schemas.player_detail import PlayerDetailOut, PlayerSeasonStatOut
from app.core.highlightly import HighlightlyClient
from app.config import get_settings

router = APIRouter(prefix="/players", tags=["players"])


async def _enrich_player(player: Player, db: AsyncSession):
    """按需从 Highlightly 补充球员丰富主数据（身高/国籍/出生日期/俱乐部/位置等）

    仅在缺失关键字段时调用，避免重复请求；补充的内容会在请求结束时随 db 提交落库。
    """
    from loguru import logger

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )
    try:
        data = await client.get_player_by_id(player.id)
        if not data:
            return
        profile = data.get("profile") or {}
        pos = profile.get("position") or {}
        club = profile.get("club") or {}
        if not player.name:
            player.name = data.get("name")
        if not player.full_name:
            player.full_name = data.get("fullName")
        if not player.logo:
            player.logo = data.get("logo")
        if not player.position_main:
            player.position_main = pos.get("main")
        if not player.position_secondary:
            player.position_secondary = pos.get("secondary")
        if not player.height:
            player.height = profile.get("height")
        if not player.citizenship:
            player.citizenship = profile.get("citizenship")
        if not player.birth_date:
            player.birth_date = profile.get("birthDate")
        if not player.club:
            player.club = club.get("current")
        await db.flush()
    except Exception as e:
        logger.warning(f"Enrich player {player.id} failed: {e}")
    finally:
        await client.close()


def _split_positions(text: Optional[str]) -> list[str]:
    """将逗号分隔的位置字符串拆分为独立位置（处理多位置场景）"""
    if not text:
        return []
    return [p.strip() for p in text.split(",") if p.strip()]


@router.get("/{player_id}", response_model=PlayerDetailOut)
async def get_player_detail(
    player_id: int,
    league_id: Optional[int] = Query(None, description="限定联赛 ID；为空返回该球员所有联赛统计"),
    db: AsyncSession = Depends(get_db),
):
    """获取球员详情：基础主数据 + 各联赛赛季统计

    若球员未入库或丰富字段缺失，则按需从 Highlightly 补充并落库。
    返回的中文名字段（cn_name / position_*_cn / club_cn_name / team_cn_name）优先取数据库映射。
    """
    player = (await db.execute(select(Player).where(Player.id == player_id))).scalar_one_or_none()
    if player is None:
        # 占位对象，补充字段后随 db 提交落库
        player = Player(id=player_id)
        db.add(player)

    # 仅在缺少丰富字段时补充（基础 name 由 box-score 同步已写入）
    if not player.height or not player.citizenship or not player.club:
        await _enrich_player(player, db)

    if league_id is not None:
        rows = (
            await db.execute(
                select(PlayerSeasonStat).where(
                    PlayerSeasonStat.player_id == player_id,
                    PlayerSeasonStat.league_id == league_id,
                )
            )
        ).scalars().all()
    else:
        rows = (
            await db.execute(
                select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == player_id)
            )
        ).scalars().all()

    league_ids = [r.league_id for r in rows]
    league_names: dict[int, str] = {}
    if league_ids:
        lrows = (
            await db.execute(select(League.id, League.cn_name, League.name).where(League.id.in_(league_ids)))
        ).all()
        league_names = {lid: (cn or nm) for lid, cn, nm in lrows}

    # 一次性查询赛季统计涉及的位置中文映射（多位置逗号拆分）
    position_keys = set()
    for r in rows:
        position_keys.update(_split_positions(r.position))
    position_keys.update(_split_positions(player.position_main))
    position_keys.update(_split_positions(player.position_secondary))
    position_cn_map: dict[str, str] = {}
    if position_keys:
        mrows = (
            await db.execute(
                select(CnMapping.key, CnMapping.cn_value).where(
                    CnMapping.category == "position",
                    CnMapping.key.in_(position_keys),
                )
            )
        ).all()
        position_cn_map = {k: v for k, v in mrows}

    # 一次性查询赛季统计涉及的球队中文名（team_id 为 Highlightly 球队 id）
    highlightly_team_ids = {r.team_id for r in rows if r.team_id}
    team_cn_map: dict[int, str] = {}
    if highlightly_team_ids:
        trows = (
            await db.execute(
                select(Team.highlightly_team_id, Team.cn_name).where(
                    Team.highlightly_team_id.in_(highlightly_team_ids),
                    Team.cn_name.is_not(None),
                )
            )
        ).all()
        team_cn_map = {tid: cn for tid, cn in trows}

    # 俱乐部中文名：按俱乐部名称匹配 teams 表
    club_cn_name: Optional[str] = None
    if player.club:
        club_team = (
            await db.execute(select(Team.cn_name).where(Team.name == player.club))
        ).scalar_one_or_none()
        if club_team:
            club_cn_name = club_team

    # 多位置字段：按逗号拆分后分别取中文，再拼接展示
    position_secondary_cn = (
        ", ".join(
            position_cn_map.get(p, p) for p in _split_positions(player.position_secondary)
        )
        if player.position_secondary
        else None
    )

    stats = [
        PlayerSeasonStatOut(
            league_id=r.league_id,
            league_name=league_names.get(r.league_id),
            season=r.season,
            team_name=r.team_name,
            team_cn_name=team_cn_map.get(r.team_id) if r.team_id else None,
            team_logo=r.team_logo,
            position=r.position,
            position_cn=position_cn_map.get(r.position) if r.position else None,
            games_played=r.games_played,
            minutes_played=r.minutes_played,
            goals=r.goals,
            assists=r.assists,
            yellow_cards=r.yellow_cards,
            red_cards=r.red_cards,
            second_yellow=r.second_yellow,
            shots_total=r.shots_total,
            shots_on_target=r.shots_on_target,
        )
        for r in rows
    ]

    return PlayerDetailOut(
        id=player.id,
        name=player.name or "",
        cn_name=player.cn_name,
        full_name=player.full_name,
        logo=player.logo,
        position_main=player.position_main,
        position_main_cn=position_cn_map.get(player.position_main) if player.position_main else None,
        position_secondary=player.position_secondary,
        position_secondary_cn=position_secondary_cn,
        height=player.height,
        citizenship=player.citizenship,
        birth_date=player.birth_date,
        club=player.club,
        club_cn_name=club_cn_name,
        stats=stats,
    )
