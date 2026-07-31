"""Telegram 每日推送服务

每日定时推送比赛信息和预测结果到 Telegram。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, List, Tuple

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.league import League
from app.models.team import Team
from app.services.telegram_service import get_telegram_service
from app.services.telegram_formatter import (
    format_daily_summary,
    format_finished_matches_summary,
    format_leaderboard_update,
    format_error_message,
)


async def get_today_matches(session: AsyncSession) -> list[dict]:
    """获取今日比赛

    Returns:
        list[dict]: 今日比赛列表
    """
    # 获取北京时间今天 00:00 到 23:59
    cn_tz = timezone(timedelta(hours=8))
    now_cn = datetime.now(cn_tz)
    today_start = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # 转换为 UTC
    utc_start = today_start.astimezone(timezone.utc)
    utc_end = today_end.astimezone(timezone.utc)

    # 查询今日比赛
    query = (
        select(
            Match.id,
            Match.match_time,
            Match.status,
            Match.home_score,
            Match.away_score,
            League.name.label("league_name"),
            Team.name.label("home_team"),
        )
        .join(League, Match.league_id == League.id)
        .join(Team, Match.home_team_id == Team.id)
        .where(
            and_(
                Match.match_time >= utc_start,
                Match.match_time < utc_end,
            )
        )
        .order_by(Match.match_time)
    )

    result = await session.execute(query)
    rows = result.all()

    # 获取客队名称
    matches = []
    for row in rows:
        # 单独查询客队名称
        away_query = select(Team.name).where(Team.id == Match.away_team_id)
        away_result = await session.execute(
            select(Team.name).where(Team.id == row.id)
        )

        # 重新查询完整数据
        match_query = (
            select(
                Match.id,
                Match.match_time,
                Match.status,
                Match.home_score,
                Match.away_score,
                Match.home_team_id,
                Match.away_team_id,
                League.name.label("league_name"),
            )
            .join(League, Match.league_id == League.id)
            .where(Match.id == row.id)
        )
        match_result = await session.execute(match_query)
        match_row = match_result.first()

        if match_row:
            # 获取主客队名称
            home_team_result = await session.execute(
                select(Team.name).where(Team.id == match_row.home_team_id)
            )
            away_team_result = await session.execute(
                select(Team.name).where(Team.id == match_row.away_team_id)
            )

            home_team = home_team_result.scalar() or "未知"
            away_team = away_team_result.scalar() or "未知"

            matches.append({
                "id": match_row.id,
                "match_time": match_row.match_time,
                "status": match_row.status,
                "home_score": match_row.home_score,
                "away_score": match_row.away_score,
                "league_name": match_row.league_name,
                "home_team": home_team,
                "away_team": away_team,
            })

    return matches


async def get_matches_with_teams(session: AsyncSession, matches_query) -> list[dict]:
    """通用：从查询结果获取比赛列表（含主客队名称）"""
    result = await session.execute(matches_query)
    rows = result.all()

    matches = []
    for row in rows:
        # 获取主客队名称
        home_result = await session.execute(
            select(Team.name).where(Team.id == row.home_team_id)
        )
        away_result = await session.execute(
            select(Team.name).where(Team.id == row.away_team_id)
        )

        matches.append({
            "id": row.id,
            "match_time": row.match_time,
            "status": row.status,
            "home_score": row.home_score,
            "away_score": row.away_score,
            "league_name": row.league_name,
            "home_team": home_result.scalar() or "未知",
            "away_team": away_result.scalar() or "未知",
        })

    return matches


async def get_yesterday_finished_matches(session: AsyncSession) -> list[dict]:
    """获取昨日已结束比赛

    Returns:
        list[dict]: 昨日已结束比赛列表
    """
    cn_tz = timezone(timedelta(hours=8))
    now_cn = datetime.now(cn_tz)
    yesterday_start = (now_cn - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)

    utc_start = yesterday_start.astimezone(timezone.utc)
    utc_end = yesterday_end.astimezone(timezone.utc)

    query = (
        select(
            Match.id,
            Match.match_time,
            Match.status,
            Match.home_score,
            Match.away_score,
            Match.home_team_id,
            Match.away_team_id,
            League.name.label("league_name"),
        )
        .join(League, Match.league_id == League.id)
        .where(
            and_(
                Match.match_time >= utc_start,
                Match.match_time < utc_end,
                Match.status == "finished",
            )
        )
        .order_by(Match.match_time)
    )

    return await get_matches_with_teams(session, query)


async def get_match_predictions(session: AsyncSession, match_ids: list[int]) -> dict[int, list[dict]]:
    """获取比赛预测

    Args:
        match_ids: 比赛 ID 列表

    Returns:
        dict: 比赛 ID -> 预测列表
    """
    if not match_ids:
        return {}

    from app.models.ai_model import AIModel

    query = (
        select(
            Prediction.match_id,
            Prediction.result,
            Prediction.score_home,
            Prediction.score_away,
            Prediction.confidence,
            AIModel.name.label("model_name"),
        )
        .join(AIModel, Prediction.model_id == AIModel.id)
        .where(Prediction.match_id.in_(match_ids))
        .order_by(Prediction.match_id, AIModel.name)
    )

    result = await session.execute(query)
    rows = result.all()

    predictions: dict[int, list[dict]] = {}
    for row in rows:
        if row.match_id not in predictions:
            predictions[row.match_id] = []

        # 将 PredictionResult 枚举转换为字符串
        result_str = row.result.value if row.result else None

        predictions[row.match_id].append({
            "model_name": row.model_name,
            "predicted_result": result_str,
            "predicted_home_score": row.score_home,
            "predicted_away_score": row.score_away,
            "confidence": row.confidence,
        })

    return predictions


async def get_ai_leaderboard(session: AsyncSession, top_n: int = 10) -> list[dict]:
    """获取 AI 排行榜

    Args:
        top_n: 获取前 N 名

    Returns:
        list[dict]: AI 排行榜列表
    """
    from app.models.ai_model import AIModel
    from sqlalchemy import case

    # 计算每个模型的命中率
    # 使用 case 表达式替代 func.cast
    query = (
        select(
            AIModel.id,
            AIModel.name.label("model_name"),
            func.count(Prediction.id).label("total"),
            func.sum(
                case(
                    (Prediction.is_correct_result == True, 1),
                    else_=0,
                )
            ).label("correct_results"),
            func.sum(
                case(
                    (Prediction.is_correct_score == True, 1),
                    else_=0,
                )
            ).label("correct_scores"),
        )
        .join(Prediction, AIModel.id == Prediction.model_id)
        .where(Prediction.calculated_at.isnot(None))
        .group_by(AIModel.id, AIModel.name)
        .order_by(
            func.sum(
                case(
                    (Prediction.is_correct_result == True, 1),
                    else_=0,
                )
            ).desc()
        )
        .limit(top_n)
    )

    result = await session.execute(query)
    rows = result.all()

    leaderboard = []
    for row in rows:
        total = row.total or 0
        correct_results = row.correct_results or 0
        correct_scores = row.correct_scores or 0

        result_accuracy = round(correct_results * 100 / total, 1) if total > 0 else 0
        score_accuracy = round(correct_scores * 100 / total, 1) if total > 0 else 0

        leaderboard.append({
            "model_name": row.model_name,
            "total_predictions": total,
            "result_accuracy": result_accuracy,
            "score_accuracy": score_accuracy,
        })

    # 按胜负命中率排序
    leaderboard.sort(key=lambda x: x["result_accuracy"], reverse=True)

    return leaderboard


def _channel_footer() -> str:
    """公共频道每条消息末尾附带的合规免责声明（海外版：模型输出仅供参考）。"""
    return (
        "\n\n─ ─ ─\n"
        "⚠️ _模型输出仅供参考，不构成任何投注建议。_"
    )


async def build_daily_messages() -> List[Tuple[str, str]]:
    """构建每日推送消息列表（仅构建，不发送），供 daily_push 与预览接口复用。

    Returns:
        list[tuple[str, str]]: [(标题, 消息正文), ...]
    """
    async with async_session_factory() as session:
        # 获取北京时间日期字符串
        cn_tz = timezone(timedelta(hours=8))
        now_cn = datetime.now(cn_tz)
        date_str = now_cn.strftime("%Y年%m月%d日")

        # 1. 获取今日比赛和预测
        today_matches = await get_today_matches(session)
        today_match_ids = [m["id"] for m in today_matches]
        today_predictions = await get_match_predictions(session, today_match_ids)
        today_message = format_daily_summary(today_matches, today_predictions, date_str)

        # 2. 获取昨日赛果
        yesterday_matches = await get_yesterday_finished_matches(session)
        yesterday_message = format_finished_matches_summary(yesterday_matches)

        # 3. 获取 AI 排行榜
        leaderboard = await get_ai_leaderboard(session, top_n=5)
        leaderboard_message = format_leaderboard_update(leaderboard, top_n=5)

        messages: List[Tuple[str, str]] = []
        if today_matches:
            messages.append(("📅 今日比赛", today_message))
        else:
            messages.append(("📅 今日比赛", f"📅 *{date_str}*\n\n今日暂无比赛安排"))

        if yesterday_matches:
            messages.append(("📋 昨日赛果", yesterday_message))

        if now_cn.weekday() == 0:  # 每周一推送排行榜
            messages.append(("📊 AI 排行榜", leaderboard_message))

        return messages


async def daily_push():
    """每日推送任务

    推送内容：
    1. 今日比赛和预测 → 公共频道 + 监控 Chat
    2. 昨日赛果 → 公共频道 + 监控 Chat
    3. AI 排行榜（每周一）→ 公共频道 + 监控 Chat
    """
    logger.info("开始执行 Telegram 每日推送任务")

    telegram = get_telegram_service()

    if not telegram.settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram Bot Token 未配置，跳过推送")
        return

    try:
        messages = await build_daily_messages()

        # 监控 Chat 广播（不含公共频道，避免重复）
        if telegram.settings.TELEGRAM_CHAT_IDS:
            for _title, message in messages:
                await telegram.broadcast(message)

        # 公共频道自动化发帖（核心交付）
        public_id = telegram.settings.TELEGRAM_PUBLIC_CHANNEL_ID
        if public_id:
            footer = _channel_footer()
            channel_ok = 0
            for _title, message in messages:
                ok = await telegram.send_to_public_channel(message + footer)
                if ok:
                    channel_ok += 1
            logger.info(f"公共频道发送完成: {channel_ok}/{len(messages)} 条")
        else:
            logger.warning("TELEGRAM_PUBLIC_CHANNEL_ID 未配置，跳过公共频道发送")

        logger.info(f"Telegram 每日推送完成: 共 {len(messages)} 条消息")

    except Exception as e:
        logger.error(f"Telegram 每日推送失败: {e}")
        try:
            error_message = format_error_message(str(e))
            await telegram.broadcast(error_message)
        except Exception:
            pass
        raise


async def push_match_reminder(match_id: int):
    """比赛提醒推送

    在比赛开始前推送提醒。

    Args:
        match_id: 比赛 ID
    """
    logger.info(f"推送比赛提醒: match_id={match_id}")

    telegram = get_telegram_service()

    if not telegram.settings.TELEGRAM_BOT_TOKEN or not telegram.settings.TELEGRAM_CHAT_IDS:
        logger.warning("Telegram 配置不完整，跳过比赛提醒")
        return

    try:
        async with async_session_factory() as session:
            # 获取比赛信息
            query = (
                select(
                    Match.id,
                    Match.match_time,
                    Match.status,
                    Match.home_team_id,
                    Match.away_team_id,
                    League.name.label("league_name"),
                )
                .join(League, Match.league_id == League.id)
                .where(Match.id == match_id)
            )

            result = await session.execute(query)
            match = result.first()

            if not match:
                logger.warning(f"比赛不存在: {match_id}")
                return

            # 获取主客队名称
            home_result = await session.execute(
                select(Team.name).where(Team.id == match.home_team_id)
            )
            away_result = await session.execute(
                select(Team.name).where(Team.id == match.away_team_id)
            )

            home_team = home_result.scalar() or "未知"
            away_team = away_result.scalar() or "未知"

            # 获取预测
            predictions = await get_match_predictions(session, [match_id])
            preds = predictions.get(match_id, [])

            # 格式化消息
            cn_tz = timezone(timedelta(hours=8))
            match_time_cn = match.match_time.astimezone(cn_tz)
            time_str = match_time_cn.strftime("%H:%M")

            message_lines = [
                f"⏰ *比赛提醒*",
                f"",
                f"🏆 {match.league_name}",
                f"🕐 今日 {time_str}",
                f"",
                f"*{home_team}* vs *{away_team}*",
                "",
            ]

            if preds:
                # 统计预测结果
                result_counts = {"home": 0, "draw": 0, "away": 0}
                for pred in preds:
                    r = pred.get("predicted_result", "")
                    # 标准化结果格式
                    if r in ("home_win", "home"):
                        result_counts["home"] += 1
                    elif r in ("draw",):
                        result_counts["draw"] += 1
                    elif r in ("away_win", "away"):
                        result_counts["away"] += 1

                consensus = max(result_counts, key=result_counts.get)
                consensus_label = {"home": "主胜", "draw": "平局", "away": "客胜"}.get(consensus, "")
                consensus_emoji = {"home": "🏠", "draw": "🤝", "away": "✈️"}.get(consensus, "")

                message_lines.append(f"🤖 AI 共识: {consensus_emoji} *{consensus_label}*")
                message_lines.append(f"📊 预测模型: {len(preds)} 个")

            message = "\n".join(message_lines)
            await telegram.broadcast(message)

            logger.info(f"比赛提醒推送成功: {match_id}")

    except Exception as e:
        logger.error(f"比赛提醒推送失败: {e}")
