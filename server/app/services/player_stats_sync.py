"""球员盒子分同步服务

- sync_box_score_for_match: 拉取单场 box-score 写入 match_player_stats（幂等），
  并顺带 upsert players 主数据基础字段（来自 box-score，无额外 API 调用）。
- sync_player_stats_for_league / sync_all_player_stats: 全量重建某联赛 / 所有联赛的
  match_player_stats，并在结束后重建 player_season_stats 聚合快照。
- sync_player_master_and_season_stats: 轻量 admin 入口，仅由现有 match_player_stats
  重建 player_season_stats 快照（不重新拉取 box-score，省 API 配额）。
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select, delete, func

from app.database import async_session_factory
from app.models.match import Match, MatchStatus
from app.models.league import League
from app.models.match_player_stat import MatchPlayerStat
from app.models.data_detail import Player, PlayerSeasonStat


def _parse_box_score(data: list[dict], match: Match) -> list[dict]:
    """解析 box-score 响应为 match_player_stats 行字典"""
    rows: list[dict] = []
    for team_block in data or []:
        team = team_block.get("team") or {}
        team_id = team.get("id")
        team_name = team.get("name")
        team_logo = team.get("logo")
        for p in team_block.get("players") or []:
            # Highlightly 实际返回 statistics 为 dict（非文档所说的 list[{...}]）
            stats = p.get("statistics") or {}
            st = stats[0] if isinstance(stats, list) else stats
            rows.append(
                {
                    "match_id": match.id,
                    "league_id": match.league_id or 0,
                    "player_id": p.get("id"),
                    "player_name": p.get("name") or p.get("fullName") or "未知球员",
                    "player_logo": p.get("logo"),
                    "team_id": team_id,
                    "team_name": team_name,
                    "team_logo": team_logo,
                    "position": p.get("position"),
                    "shirt_number": p.get("shirtNumber"),
                    "is_captain": bool(p.get("isCaptain")),
                    "is_substitute": bool(p.get("isSubstitute")),
                    "minutes_played": p.get("minutesPlayed") or 0,
                    "goals": st.get("goalsScored") or 0,
                    "assists": st.get("assists") or 0,
                    # 第二张黄牌等同于被罚下，计入红牌
                    "red_cards": (st.get("cardsRed") or 0) + (st.get("cardsSecondYellow") or 0),
                    "yellow_cards": st.get("cardsYellow") or 0,
                    "second_yellow": st.get("cardsSecondYellow") or 0,
                    "shots_total": st.get("shotsTotal") or 0,
                    "shots_on_target": st.get("shotsOnTarget") or 0,
                    "shots_off_target": st.get("shotsOffTarget") or 0,
                }
            )
    return rows


async def _upsert_players(session, rows: list[dict]):
    """根据 box-score 行 upsert players 基础主数据（不覆盖已丰富的字段）

    注意：cn_name（球员中文名）直接落在 players 表，由独立的回填/维护流程写入，
    这里只负责基础字段，不触碰 cn_name，避免覆盖已有中文名。
    """
    pids = [r["player_id"] for r in rows if r.get("player_id")]
    if not pids:
        return
    existing = {
        p.id: p
        for p in (await session.execute(select(Player).where(Player.id.in_(pids)))).scalars().all()
    }
    for r in rows:
        pid = r.get("player_id")
        if not pid:
            continue
        p = existing.get(pid)
        if p is None:
            session.add(
                Player(
                    id=pid,
                    name=r.get("player_name"),
                    logo=r.get("player_logo"),
                    position_main=r.get("position"),
                )
            )
            existing[pid] = True
        else:
            if not p.name:
                p.name = r.get("player_name")
            if not p.logo:
                p.logo = r.get("player_logo")
            if not p.position_main:
                p.position_main = r.get("position")


async def sync_box_score_for_match(match: Match) -> int:
    """拉取并存储单场比赛的 box-score（按 match_id 幂等 upsert）"""
    from app.core.highlightly import HighlightlyClient
    from app.config import get_settings

    if not match.highlightly_id:
        return 0

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )
    try:
        data = await client.get_box_score(match.highlightly_id)
    except Exception as e:
        logger.warning(
            f"Box-score fetch failed for match {match.id} (hl={match.highlightly_id}): "
            f"{type(e).__name__}: {e}"
        )
        return 0
    finally:
        await client.close()

    rows = _parse_box_score(data, match)
    if not rows:
        return 0

    async with async_session_factory() as session:
        # 删除该场比赛已有记录后整场重插（幂等）
        await session.execute(delete(MatchPlayerStat).where(MatchPlayerStat.match_id == match.id))
        session.add_all([MatchPlayerStat(**r) for r in rows])
        await _upsert_players(session, rows)
        await session.commit()

    logger.info(f"Box-score synced for match {match.id}: {len(rows)} players")
    return len(rows)


async def rebuild_player_season_stats_for_league(league: League) -> int:
    """由 match_player_stats 聚合重建某联赛的 player_season_stats 快照（幂等）"""
    async with async_session_factory() as session:
        stmt = (
            select(
                MatchPlayerStat.player_id,
                func.max(MatchPlayerStat.player_name).label("player_name"),
                func.max(MatchPlayerStat.player_logo).label("player_logo"),
                func.max(MatchPlayerStat.team_name).label("team_name"),
                func.max(MatchPlayerStat.team_logo).label("team_logo"),
                func.max(MatchPlayerStat.position).label("position"),
                func.coalesce(func.sum(MatchPlayerStat.minutes_played), 0).label("minutes_played"),
                func.coalesce(func.sum(MatchPlayerStat.goals), 0).label("goals"),
                func.coalesce(func.sum(MatchPlayerStat.assists), 0).label("assists"),
                func.coalesce(func.sum(MatchPlayerStat.yellow_cards), 0).label("yellow_cards"),
                func.coalesce(func.sum(MatchPlayerStat.red_cards), 0).label("red_cards"),
                func.coalesce(func.sum(MatchPlayerStat.second_yellow), 0).label("second_yellow"),
                func.coalesce(func.sum(MatchPlayerStat.shots_total), 0).label("shots_total"),
                func.coalesce(func.sum(MatchPlayerStat.shots_on_target), 0).label("shots_on_target"),
                func.count(func.distinct(MatchPlayerStat.match_id)).label("games_played"),
            )
            .where(MatchPlayerStat.league_id == league.id)
            .group_by(MatchPlayerStat.player_id)
        )
        rows = (await session.execute(stmt)).all()

        # 计算每个球员出场场次最多的球队（主力球队），用于填充 team_id
        team_stmt = (
            select(
                MatchPlayerStat.player_id,
                MatchPlayerStat.team_id,
                func.count(func.distinct(MatchPlayerStat.match_id)).label("cnt"),
            )
            .where(MatchPlayerStat.league_id == league.id, MatchPlayerStat.team_id.isnot(None))
            .group_by(MatchPlayerStat.player_id, MatchPlayerStat.team_id)
        )
        team_rows = (await session.execute(team_stmt)).all()
        _by_player: dict[int, dict[int, int]] = {}
        for r in team_rows:
            _by_player.setdefault(r.player_id, {})[r.team_id] = r.cnt
        primary_team: dict[int, Optional[int]] = {
            pid: max(tc.items(), key=lambda kv: kv[1])[0]
            for pid, tc in _by_player.items()
        }

        await session.execute(
            delete(PlayerSeasonStat).where(
                PlayerSeasonStat.league_id == league.id,
                PlayerSeasonStat.season == league.season,
            )
        )
        new_rows = [
            PlayerSeasonStat(
                league_id=league.id,
                season=league.season,
                player_id=r.player_id,
                player_name=r.player_name,
                player_logo=r.player_logo,
                team_id=primary_team.get(r.player_id),
                team_name=r.team_name,
                team_logo=r.team_logo,
                position=r.position,
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
        session.add_all(new_rows)
        await session.commit()
        return len(new_rows)


async def sync_player_stats_for_league(league: League) -> int:
    """全量重建某联赛所有已结束比赛的球员统计，并重建赛季快照"""
    async with async_session_factory() as session:
        stmt = (
            select(Match)
            .where(Match.league_id == league.id, Match.status == MatchStatus.finished)
            .order_by(Match.match_time)
        )
        result = await session.execute(stmt)
        matches = result.scalars().all()

    total = 0
    for m in matches:
        try:
            total += await sync_box_score_for_match(m)
        except Exception as e:
            logger.warning(f"Box-score sync failed for match {m.id}: {type(e).__name__}: {e}")

    season_count = 0
    try:
        season_count = await rebuild_player_season_stats_for_league(league)
    except Exception as e:
        logger.error(f"Season stats rebuild failed for {league.cn_name}: {e}")

    logger.info(
        f"Player stats rebuilt for league {league.cn_name}: "
        f"{total} player-rows, {season_count} season-stats"
    )
    return total


async def sync_all_player_stats(league_ids: Optional[list[int]] = None) -> dict:
    """全量重建球员统计（admin 手动触发用）

    Args:
        league_ids: 指定重建的联赛（本地 id）列表；为 None 时重建所有 is_active 联赛。
                    用于回填历史赛季（如 2025 赛季的非活跃联赛副本）。
    """
    from typing import Optional
    async with async_session_factory() as session:
        if league_ids:
            leagues = (
                await session.execute(select(League).where(League.id.in_(league_ids)))
            ).scalars().all()
        else:
            leagues = (
                await session.execute(select(League).where(League.is_active == True))  # noqa: E712
            ).scalars().all()

    per_league: list[dict] = []
    for lg in leagues:
        try:
            count = await sync_player_stats_for_league(lg)
            per_league.append({"league": lg.cn_name, "players": count})
        except Exception as e:
            logger.error(f"Player stats sync failed for {lg.cn_name}: {e}")
            per_league.append({"league": lg.cn_name, "error": str(e)})

    return {"leagues": per_league}


async def sync_player_master_and_season_stats() -> dict:
    """轻量重建：仅由现有 match_player_stats 重算 player_season_stats 快照

    不重新拉取 box-score，节省 API 配额；用于已同步过逐场盒子分后重算排名。
    """
    async with async_session_factory() as session:
        leagues = (
            await session.execute(select(League).where(League.is_active == True))  # noqa: E712
        ).scalars().all()

    per_league: list[dict] = []
    for lg in leagues:
        try:
            n = await rebuild_player_season_stats_for_league(lg)
            per_league.append({"league": lg.cn_name, "season_stats": n})
        except Exception as e:
            logger.error(f"Season stats rebuild failed for {lg.cn_name}: {e}")
            per_league.append({"league": lg.cn_name, "error": str(e)})

    return {"leagues": per_league}
