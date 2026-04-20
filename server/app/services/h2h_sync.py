"""H2H（Head-to-Head）数据同步服务"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.highlightly import HighlightlyClient
from app.database import async_session_factory
from app.models.head_to_head import HeadToHead


async def sync_all_h2h():
    """同步所有 upcoming 比赛的 H2H 数据（admin 手动触发用）

    查询所有 status="upcoming" 的比赛，获取两队的交锋历史数据，
    存储到 head_to_head 表中。

    Returns:
        dict: 同步结果统计
    """
    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
        league_id=settings.HIGHLIGHTLY_LEAGUE_ID,
        season=settings.HIGHLIGHTLY_SEASON,
    )

    stats = {
        "upcoming_matches": 0,
        "synced": 0,
        "skipped": 0,
        "failed": 0,
    }

    try:
        from app.models.match import Match, MatchStatus

        async with async_session_factory() as session:
            stmt = (
                select(Match)
                .where(Match.status == MatchStatus.upcoming)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
            )
            result = await session.execute(stmt)
            upcoming_matches = result.scalars().all()

            stats["upcoming_matches"] = len(upcoming_matches)
            logger.info(f"Found {len(upcoming_matches)} upcoming matches to process")

            for match in upcoming_matches:
                home = match.home_team
                away = match.away_team

                if not home or not away:
                    logger.warning(f"Match {match.id}: missing team data")
                    stats["skipped"] += 1
                    continue

                if not home.highlightly_team_id or not away.highlightly_team_id:
                    logger.warning(
                        f"Match {match.id} ({home.name} vs {away.name}): "
                        f"missing highlightly_team_id"
                    )
                    stats["skipped"] += 1
                    continue

                t1, t2 = sorted([home.id, away.id])

                stmt_h2h = select(HeadToHead).where(
                    HeadToHead.team_one_id == t1,
                    HeadToHead.team_two_id == t2,
                )
                h2h_result = await session.execute(stmt_h2h)
                existing = h2h_result.scalar_one_or_none()

                if existing and existing.matches:
                    logger.info(f"H2H already exists: {home.name} vs {away.name}")
                    stats["skipped"] += 1
                    continue

                try:
                    matches_summary = await _fetch_h2h_from_api(
                        client, home.highlightly_team_id, away.highlightly_team_id
                    )

                    if not matches_summary:
                        logger.info(f"No H2H data for {home.name} vs {away.name}, skipping")
                        stats["skipped"] += 1
                        continue

                    if existing:
                        existing.matches = matches_summary
                        logger.info(f"Updated H2H: {home.name} vs {away.name}")
                    else:
                        h2h = HeadToHead(
                            team_one_id=t1,
                            team_two_id=t2,
                            matches=matches_summary,
                        )
                        session.add(h2h)
                        logger.info(f"Created H2H: {home.name} vs {away.name}")

                    stats["synced"] += 1

                except Exception as e:
                    logger.warning(f"Failed to fetch H2H for {home.name} vs {away.name}: {e}")
                    stats["failed"] += 1

            await session.commit()

        logger.info(
            f"H2H sync completed: "
            f"{stats['synced']} synced, "
            f"{stats['skipped']} skipped, "
            f"{stats['failed']} failed "
            f"(from {stats['upcoming_matches']} upcoming matches)"
        )

        return stats

    except Exception as e:
        logger.error(f"H2H sync failed: {e}")
        raise
    finally:
        await client.close()


async def sync_h2h_for_match(match_id: int):
    """为指定比赛同步 H2H 数据（新增比赛时由编排逻辑调用）

    Args:
        match_id: 本地 Match.id

    Returns:
        bool: 是否成功同步了 H2H 数据
    """
    from app.models.match import Match

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
        league_id=settings.HIGHLIGHTLY_LEAGUE_ID,
        season=settings.HIGHLIGHTLY_SEASON,
    )

    try:
        async with async_session_factory() as session:
            stmt = (
                select(Match)
                .where(Match.id == match_id)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
            )
            result = await session.execute(stmt)
            match = result.scalar_one_or_none()

            if not match:
                logger.warning(f"Match {match_id} not found for H2H sync")
                return False

            home = match.home_team
            away = match.away_team

            if not home or not away:
                logger.warning(f"Match {match_id}: missing team data")
                return False

            if not home.highlightly_team_id or not away.highlightly_team_id:
                logger.warning(
                    f"Match {match_id} ({home.name} vs {away.name}): "
                    f"missing highlightly_team_id, skip H2H sync"
                )
                return False

            t1, t2 = sorted([home.id, away.id])

            # 检查是否已有 H2H 数据
            stmt_h2h = select(HeadToHead).where(
                HeadToHead.team_one_id == t1,
                HeadToHead.team_two_id == t2,
            )
            h2h_result = await session.execute(stmt_h2h)
            existing = h2h_result.scalar_one_or_none()

            if existing and existing.matches:
                logger.info(f"H2H already exists for {home.name} vs {away.name}, skip")
                return True

            # 从 API 获取
            try:
                matches_summary = await _fetch_h2h_from_api(
                    client, home.highlightly_team_id, away.highlightly_team_id
                )
            except Exception as e:
                logger.warning(f"Failed to fetch H2H for {home.name} vs {away.name}: {e}")
                return False

            if not matches_summary:
                logger.info(f"No H2H data for {home.name} vs {away.name}")
                return False

            if existing:
                existing.matches = matches_summary
            else:
                h2h = HeadToHead(
                    team_one_id=t1,
                    team_two_id=t2,
                    matches=matches_summary,
                )
                session.add(h2h)

            await session.commit()
            logger.info(f"H2H synced for {home.name} vs {away.name}")
            return True

    except Exception as e:
        logger.error(f"H2H sync failed for match {match_id}: {e}")
        return False
    finally:
        await client.close()


# ── 内部工具 ────────────────────────────────────────────────

async def _fetch_h2h_from_api(
    client: HighlightlyClient, highlightly_team_id_one: int, highlightly_team_id_two: int
) -> list[dict]:
    """从 Highlightly API 获取 H2H 数据并精简格式"""
    h2h_data = await client.get_head_to_head(
        highlightly_team_id_one, highlightly_team_id_two
    )
    matches_summary = []
    for m in h2h_data[:10]:
        state = m.get("state", {})
        matches_summary.append({
            "date": m.get("date", "")[:10],
            "home": m.get("homeTeam", {}).get("name", ""),
            "away": m.get("awayTeam", {}).get("name", ""),
            "score": state.get("score", {}).get("current", ""),
            "status": state.get("description", ""),
        })
    return matches_summary
