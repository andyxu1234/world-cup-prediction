"""积分榜同步服务 — 将 Highlightly /standings 落地到 league_standings 表

遍历所有活跃联赛，拉取官方积分榜，upsert 进 league_standings。
积分榜与球队榜统一读此表（球队榜 = 按指标排序）。
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select, delete, update

from app.database import async_session_factory
from app.models.league import League
from app.models.team import Team
from app.models.data_detail import LeagueStanding


def _to_int(v, default: int = 0) -> int:
    try:
        return int(v or default)
    except (TypeError, ValueError):
        return default


async def sync_league_standings(league_ids: Optional[list[int]] = None) -> dict:
    """全量同步官方积分榜到 league_standings（admin / pipeline 调用）

    对每个联赛：删除该联赛本赛季已有行后整批重插（幂等）。
    同时按 highlightly team id 回填本地 teams.highlightly_team_id，以便详情页联动。

    Args:
        league_ids: 指定同步的联赛（本地 id）列表；为 None 时同步所有 is_active 联赛。
                    用于回填历史赛季（如 2025 赛季的非活跃联赛副本）。
    """
    from app.core.highlightly import HighlightlyClient
    from app.config import get_settings
    from typing import Optional

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )

    try:
        async with async_session_factory() as read_session:
            if league_ids:
                leagues = (
                    await read_session.execute(select(League).where(League.id.in_(league_ids)))
                ).scalars().all()
            else:
                leagues = (
                    await read_session.execute(select(League).where(League.is_active == True))  # noqa: E712
                ).scalars().all()

        per_league: list[dict] = []
        total_rows = 0

        for league in leagues:
            try:
                data = await client.get_standings(league.highlightly_league_id, league.season)
            except Exception as e:
                logger.warning(
                    f"Standings sync skipped for {league.cn_name} "
                    f"(hl_id={league.highlightly_league_id}): {type(e).__name__}: {e}"
                )
                per_league.append({"league": league.cn_name, "error": str(e)})
                continue

            groups = data.get("groups", [])
            rows: list[LeagueStanding] = []

            async with async_session_factory() as session:
                # 本联赛内一次性加载球队映射，做 team_id 解析与回填
                team_rows = (
                    await session.execute(
                        select(Team.id, Team.highlightly_team_id, Team.name)
                    )
                ).all()
                team_by_hl = {r.highlightly_team_id: r.id for r in team_rows if r.highlightly_team_id}
                team_by_name = {r.name: r.id for r in team_rows if r.name}

                for group in groups:
                    group_name = group.get("name", "") or ""
                    for s in group.get("standings", []):
                        team_info = s.get("team", {}) or {}
                        hl_team_id = team_info.get("id")
                        total = s.get("total", {}) or {}
                        home = s.get("home", {}) or {}
                        away = s.get("away", {}) or {}

                        local_team_id = team_by_hl.get(hl_team_id)
                        if local_team_id is None and hl_team_id:
                            # 按队名回填 highlightly_team_id
                            name = team_info.get("name")
                            tid = team_by_name.get(name) if name else None
                            if tid is not None:
                                await session.execute(
                                    update(Team)
                                    .where(Team.id == tid)
                                    .values(highlightly_team_id=hl_team_id)
                                )
                                team_by_hl[hl_team_id] = tid
                                local_team_id = tid

                        gf = _to_int(total.get("scoredGoals"))
                        ga = _to_int(total.get("receivedGoals"))
                        rows.append(
                            LeagueStanding(
                                league_id=league.id,
                                season=league.season,
                                group_name=group_name,
                                team_id=local_team_id,
                                highlightly_team_id=hl_team_id,
                                team_name=team_info.get("name"),
                                team_logo=team_info.get("logo"),
                                position=_to_int(s.get("position")),
                                played=_to_int(total.get("games")),
                                won=_to_int(total.get("wins")),
                                draw=_to_int(total.get("draws")),
                                lost=_to_int(total.get("loses")),
                                goals_for=gf,
                                goals_against=ga,
                                goal_diff=gf - ga,
                                points=_to_int(s.get("points")),
                                home_won=_to_int(home.get("wins")),
                                home_draw=_to_int(home.get("draws")),
                                home_lost=_to_int(home.get("loses")),
                                home_gf=_to_int(home.get("scoredGoals")),
                                home_ga=_to_int(home.get("receivedGoals")),
                                away_won=_to_int(away.get("wins")),
                                away_draw=_to_int(away.get("draws")),
                                away_lost=_to_int(away.get("loses")),
                                away_gf=_to_int(away.get("scoredGoals")),
                                away_ga=_to_int(away.get("receivedGoals")),
                            )
                        )

                # 幂等：删除该联赛本赛季已有行，再整批插入
                await session.execute(
                    delete(LeagueStanding).where(
                        LeagueStanding.league_id == league.id,
                        LeagueStanding.season == league.season,
                    )
                )
                session.add_all(rows)
                await session.commit()

            total_rows += len(rows)
            per_league.append({"league": league.cn_name, "rows": len(rows)})
            logger.info(f"League standings synced for {league.cn_name}: {len(rows)} rows")

        return {"leagues": per_league, "total_rows": total_rows}
    except Exception as e:
        logger.error(f"League standings sync failed: {e}")
        raise
    finally:
        await client.close()
