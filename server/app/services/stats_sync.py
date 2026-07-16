"""足球统计数据同步服务 — 球队统计、近期状态

提供两个入口：
- sync_standings_and_stats(): 全量同步（admin 手动触发用）
- sync_stats_for_teams(): 精确同步指定球队（编排逻辑用）
"""

from __future__ import annotations

from loguru import logger
from typing import Optional

from app.database import async_session_factory
from app.models.team import Team
from app.models.league import League, LeagueType


async def sync_standings_and_stats():
    """全量同步：遍历所有活跃联赛的积分榜 + 球队赛季统计 + 近期状态（admin 手动触发用）

    不再写死世界杯联赛 ID：
    - 遍历 leagues 表中 is_active=True 的联赛，逐个拉取 standings 并回填球队的
      highlightly_team_id（以及杯赛类型的 group_name）。
    - 球队赛季统计的 from_date 由各球队所属联赛的 season 决定（见 _sync_team_stats_batch）。
    """
    from app.core.highlightly import HighlightlyClient
    from app.config import get_settings
    from sqlalchemy import select

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )

    try:
        # 0. 取所有活跃联赛
        async with async_session_factory() as session:
            leagues = (
                await session.execute(select(League).where(League.is_active == True))  # noqa: E712
            ).scalars().all()
        league_seasons = {lg.id: lg.season for lg in leagues}

        # 1. 逐个活跃联赛拉取积分榜，回填球队 highlightly_team_id / group_name
        total_groups = 0
        for league in leagues:
            try:
                standings_data = await client.get_standings(
                    league.highlightly_league_id, league.season
                )
            except Exception as e:
                logger.warning(
                    f"Standings sync skipped for league {league.cn_name} "
                    f"(hl_id={league.highlightly_league_id}): {e}"
                )
                continue

            groups = standings_data.get("groups", [])
            total_groups += len(groups)

            async with async_session_factory() as session:
                for group in groups:
                    group_name = group.get("name", "")
                    short_name = group_name.split(" - ")[0].replace("Group ", "").strip()

                    for standing in group.get("standings", []):
                        team_info = standing.get("team", {})
                        team_name = team_info.get("name")

                        if team_name:
                            stmt = select(Team).where(Team.name == team_name)
                            result = await session.execute(stmt)
                            team = result.scalar_one_or_none()
                            if team:
                                # group_name 仅用于杯赛（世界杯小组等），联赛类型不填
                                if league.type == LeagueType.cup and not team.group_name:
                                    team.group_name = short_name
                                hl_id = team_info.get("id")
                                if hl_id and not team.highlightly_team_id:
                                    team.highlightly_team_id = hl_id

                await session.commit()
                logger.info(
                    f"Standings sync for {league.cn_name}: {len(groups)} groups"
                )

        # 2. 同步所有球队赛季统计（按所属联赛赛季计算 from_date）
        async with async_session_factory() as session:
            stmt = select(Team).where(Team.highlightly_team_id.isnot(None))
            result = await session.execute(stmt)
            teams = result.scalars().all()

            stats_count, form_count = await _sync_team_stats_batch(
                client, teams, session, settings, league_seasons
            )

            await session.commit()
            logger.info(f"Stats sync: {stats_count} teams stats, {form_count} teams form")

        return {"standings_groups": total_groups, "stats": stats_count, "form": form_count}
    except Exception as e:
        logger.error(f"Stats sync failed: {e}")
        raise
    finally:
        await client.close()


async def sync_stats_for_teams(team_ids: list[int]):
    """精确同步指定球队的 season_stats 和 recent_form

    比赛结束后调用，只更新涉及的两支球队，而非全量。

    Args:
        team_ids: 需要更新的 Team.id 列表

    Returns:
        dict: {"stats": int, "form": int}
    """
    from app.core.highlightly import HighlightlyClient
    from app.config import get_settings
    from sqlalchemy import select

    if not team_ids:
        return {"stats": 0, "form": 0}

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )

    try:
        async with async_session_factory() as session:
            stmt = select(Team).where(
                Team.id.in_(team_ids),
                Team.highlightly_team_id.isnot(None),
            )
            result = await session.execute(stmt)
            teams = result.scalars().all()

            stats_count, form_count = await _sync_team_stats_batch(client, teams, session, settings)

            await session.commit()
            logger.info(
                f"Targeted stats sync for {len(team_ids)} team IDs: "
                f"{stats_count} stats, {form_count} form updated"
            )

        return {"stats": stats_count, "form": form_count}
    except Exception as e:
        logger.error(f"Targeted stats sync failed: {e}")
        raise
    finally:
        await client.close()


# ── 内部工具 ────────────────────────────────────────────────

async def _sync_team_stats_batch(
    client, teams: list[Team], session, settings, league_seasons: dict | None = None
) -> tuple[int, int]:
    """批量同步球队的 season_stats 和 recent_form

    Args:
        league_seasons: {league_id: season} 映射，用于按球队所属联赛赛季计算
                        from_date。为 None 时回退到全局 settings.HIGHLIGHTLY_SEASON。

    Returns:
        (stats_count, form_count)
    """
    from app.core.highlightly import HighlightlyClient
    from sqlalchemy import select

    # 未显式传入时，从 DB 构建 {league_id: season} 映射（供 targeted 调用复用）
    if league_seasons is None:
        rows = (await session.execute(select(League.id, League.season))).all()
        league_seasons = {lid: ssn for lid, ssn in rows}

    stats_count = 0
    form_count = 0

    for team in teams:
        # 按球队所属联赛赛季计算统计窗口（多联赛改造）
        season = settings.HIGHLIGHTLY_SEASON
        if league_seasons and team.league_id is not None:
            season = league_seasons.get(team.league_id, settings.HIGHLIGHTLY_SEASON)

        # 同步赛季统计
        try:
            from_date = f"{season - 1}-01-01"
            stats = await client.get_team_statistics(
                team.highlightly_team_id, from_date=from_date
            )
            if stats:
                team.season_stats = stats
                stats_count += 1
        except Exception as e:
            logger.warning(f"Failed to fetch stats for {team.name}: {e}")

        # 同步最近5场
        try:
            recent = await client.get_last_five_games(team.highlightly_team_id)
            if recent:
                form_summary = []
                for m in recent[:5]:
                    state = m.get("state", {})
                    score = state.get("score", {}).get("current", "")
                    home_team = m.get("homeTeam", {}).get("name", "")
                    away_team = m.get("awayTeam", {}).get("name", "")
                    form_summary.append({
                        "date": m.get("date", "")[:10],
                        "home": home_team,
                        "away": away_team,
                        "score": score,
                        "status": state.get("description", ""),
                    })
                team.recent_form = {"matches": form_summary}
                form_count += 1
        except Exception as e:
            logger.warning(f"Failed to fetch form for {team.name}: {e}")

    return stats_count, form_count
