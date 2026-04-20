"""比赛数据同步服务 — 调 Highlightly API 获取赛程并更新数据库

返回值包含变更信息，供下游编排逻辑按需触发 H2H 同步、stats 更新、预测评估等。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from loguru import logger
from typing import Optional

from app.database import async_session_factory
from app.models.team import Team
from app.models.match import Match, MatchStatus


# ── 状态映射 ────────────────────────────────────────────────

LIVE_STATES = frozenset({
    "First half", "Second half", "Half time",
    "Extra time", "Penalties", "Break time",
    "In progress", "Suspended", "Interrupted",
})

FINISHED_STATES = frozenset({
    "Finished", "Finished after penalties",
    "Finished after extra time", "Awarded", "Abandoned",
})


def _map_status(state_desc: str) -> MatchStatus:
    """将 Highlightly 的 state.description 映射为 MatchStatus"""
    if state_desc in LIVE_STATES:
        return MatchStatus.live
    if state_desc in FINISHED_STATES:
        return MatchStatus.finished
    return MatchStatus.upcoming


def _parse_score(score_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """从 "3 - 1" 格式解析比分"""
    if not score_str:
        return None, None
    try:
        parts = score_str.split(" - ")
        return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, IndexError):
        return None, None


def _calc_result(home_score: Optional[int], away_score: Optional[int]):
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return "home_win"
    elif home_score < away_score:
        return "away_win"
    return "draw"


def _calc_match_day(match_time_str: str) -> int:
    """根据时间计算比赛日编号，兼容 ISO 8601 和 MySQL datetime 格式"""
    try:
        if "T" in match_time_str:
            dt = datetime.fromisoformat(match_time_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(match_time_str)
        world_cup_start = datetime(2026, 6, 11, tzinfo=dt.tzinfo)
        return (dt.date() - world_cup_start.date()).days + 1
    except Exception:
        return 1


# ── 同步任务 ────────────────────────────────────────────────

async def sync_matches():
    """同步世界杯比赛数据，返回变更信息供下游使用

    Returns:
        dict: {
            "synced": int,              # 总处理比赛数
            "new_matches": list[int],   # 本轮新增的比赛 ID
            "newly_finished": list[int],# 本轮状态变为 finished 的比赛 ID
        }
    """
    from app.core.highlightly import HighlightlyClient
    from app.config import get_settings

    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
        league_id=settings.HIGHLIGHTLY_LEAGUE_ID,
        season=settings.HIGHLIGHTLY_SEASON,
    )

    new_matches: list[int] = []
    newly_finished: list[int] = []

    try:
        matches = await client.get_all_world_cup_matches()
        logger.info(f"Highlightly: fetched {len(matches)} World Cup matches")

        if not matches:
            logger.warning("No matches returned from Highlightly")
            return {"synced": 0, "new_matches": [], "newly_finished": []}

        async with async_session_factory() as session:
            for match_data in matches:
                change = await _upsert_match(session, match_data)
                if change == "new":
                    new_matches.append(match_data["id"])
                elif change == "finished":
                    newly_finished.append(match_data["id"])
            await session.commit()

        logger.info(
            f"Match sync completed: {len(matches)} synced, "
            f"{len(new_matches)} new, {len(newly_finished)} newly finished"
        )
        return {
            "synced": len(matches),
            "new_matches": new_matches,
            "newly_finished": newly_finished,
        }
    except Exception as e:
        logger.error(f"Match sync failed: {e}")
        raise
    finally:
        await client.close()


# ── Upsert 逻辑 ─────────────────────────────────────────────

async def _upsert_match(session, match_data: dict) -> Optional[str]:
    """单场比赛 upsert

    Returns:
        None: 比赛已存在且状态无变化
        "new": 新增比赛
        "finished": 比赛状态变为 finished
    """
    from sqlalchemy import select

    highlightly_id = match_data["id"]
    # Highlightly 返回 ISO 8601 格式 "2026-06-28T02:00:00.000Z"（UTC时间），转为北京时间后存入数据库
    raw_time = match_data["date"]
    # 解析 UTC 时间
    if "T" in raw_time:
        dt_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    else:
        dt_utc = datetime.fromisoformat(raw_time).replace(tzinfo=__import__('datetime').timezone.utc)
    # 转为北京时间（UTC+8）
    dt_beijing = dt_utc + timedelta(hours=8)
    match_time = dt_beijing.strftime("%Y-%m-%d %H:%M:%S")
    round_name = match_data.get("round", "小组赛")
    state = match_data.get("state", {})
    status = _map_status(state.get("description", ""))
    home_score, away_score = _parse_score(state.get("score", {}).get("current"))

    # Upsert teams
    home_team = await _upsert_team(session, match_data["homeTeam"])
    away_team = await _upsert_team(session, match_data["awayTeam"])

    # Check if match exists
    stmt = select(Match).where(Match.highlightly_id == highlightly_id)
    result = await session.execute(stmt)
    match = result.scalar_one_or_none()

    if match:
        old_status = match.status
        match.status = status
        match.home_score = home_score
        match.away_score = away_score
        if status == MatchStatus.finished:
            match.result = _calc_result(home_score, away_score)
        # 检测状态从非 finished 变为 finished
        if old_status != MatchStatus.finished and status == MatchStatus.finished:
            return "finished"
        return None
    else:
        match = Match(
            highlightly_id=highlightly_id,
            match_day=_calc_match_day(match_time),
            round=round_name,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            match_time=match_time,
            venue=None,  # 需要调用 get_match_by_id 获取详情
            status=status,
            home_score=home_score,
            away_score=away_score,
            result=_calc_result(home_score, away_score) if status == MatchStatus.finished else None,
        )
        session.add(match)
        return "new"


async def _upsert_team(session, team_data: dict) -> Team:
    """Upsert 球队 — 通过 name 匹配已有 Team，同步 logo 到 flag_url"""
    from sqlalchemy import select

    name = team_data["name"]
    logo = team_data.get("logo")
    highlightly_team_id = team_data.get("id")

    # 中文队名映射（与 Highlightly name 对应）
    _CN_NAMES = {
        'Canada': '加拿大', 'Mexico': '墨西哥', 'USA': '美国',
        'England': '英格兰', 'France': '法国', 'Croatia': '克罗地亚',
        'Portugal': '葡萄牙', 'Norway': '挪威', 'Germany': '德国',
        'Netherlands': '荷兰', 'Austria': '奥地利', 'Belgium': '比利时',
        'Scotland': '苏格兰', 'Spain': '西班牙', 'Sweden': '瑞典',
        'Turkey': '土耳其', 'Bosnia & Herzegovina': '波黑',
        'Czech Republic': '捷克', 'Switzerland': '瑞士',
        'Argentina': '阿根廷', 'Brazil': '巴西', 'Ecuador': '厄瓜多尔',
        'Uruguay': '乌拉圭', 'Colombia': '哥伦比亚', 'Paraguay': '巴拉圭',
        'Japan': '日本', 'Korea Republic': '韩国', 'IR Iran': '伊朗',
        'Saudi Arabia': '沙特阿拉伯', 'Qatar': '卡塔尔', 'Iraq': '伊拉克',
        'Jordan': '约旦', 'Australia': '澳大利亚', 'Uzbekistan': '乌兹别克斯坦',
        'Morocco': '摩洛哥', 'Tunisia': '突尼斯', 'Egypt': '埃及',
        'Algeria': '阿尔及利亚', 'Ghana': '加纳', 'Cape Verde': '佛得角',
        'South Africa': '南非', "Côte d'Ivoire": '科特迪瓦',
        'Congo DR': '刚果(金)', 'Senegal': '塞内加尔',
        'Curaçao': '库拉索', 'Haiti': '海地', 'Panama': '巴拿马',
        'New Zealand': '新西兰',
    }

    stmt = select(Team).where(Team.name == name)
    result = await session.execute(stmt)
    team = result.scalar_one_or_none()

    if team:
        # 用 Highlightly API 返回的 logo 更新 flag_url（外部 URL）
        if logo and team.flag_url != logo:
            team.flag_url = logo
        # 同步 highlightly_team_id
        if highlightly_team_id and team.highlightly_team_id != highlightly_team_id:
            team.highlightly_team_id = highlightly_team_id
        # 补充 cn_name（如果之前没有）
        if not team.cn_name and name in _CN_NAMES:
            team.cn_name = _CN_NAMES[name]
    else:
        team = Team(
            name=name,
            cn_name=_CN_NAMES.get(name),
            flag_url=logo,
            highlightly_team_id=highlightly_team_id,
        )
        session.add(team)
        await session.flush()

    return team
