"""Telegram 消息格式化

将比赛数据、预测结果格式化为 Telegram 消息。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any


def format_match_card(match: dict) -> str:
    """格式化单场比赛卡片

    Args:
        match: 比赛数据字典

    Returns:
        str: 格式化的 Markdown 消息
    """
    home_team = match.get("home_team", "未知")
    away_team = match.get("away_team", "未知")
    match_time = match.get("match_time", "")
    league_name = match.get("league_name", "")
    status = match.get("status", "")

    # 格式化时间
    time_str = ""
    if match_time:
        try:
            if isinstance(match_time, str):
                dt = datetime.fromisoformat(match_time.replace("Z", "+00:00"))
            else:
                dt = match_time
            # 转换为北京时间 (UTC+8)
            cn_tz = timezone(timedelta(hours=8))
            dt_cn = dt.astimezone(cn_tz)
            time_str = dt_cn.strftime("%m/%d %H:%M")
        except Exception:
            time_str = str(match_time)

    # 状态标签
    status_emoji = {
        "not_started": "⏰",
        "live": "🔴",
        "finished": "✅",
        "postponed": "⏸️",
        "cancelled": "❌",
    }.get(status, "❓")

    lines = []
    if league_name:
        lines.append(f"🏆 *{league_name}*")
    lines.append(f"{status_emoji} {time_str}")
    lines.append(f"*{home_team}* vs *{away_team}*")

    # 比分（已结束或进行中）
    if status in ("finished", "live"):
        home_score = match.get("home_score", "?")
        away_score = match.get("away_score", "?")
        lines.append(f"比分: {home_score} - {away_score}")

    return "\n".join(lines)


def format_prediction_summary(predictions: list[dict]) -> str:
    """格式化预测汇总

    Args:
        predictions: 预测列表

    Returns:
        str: 格式化的预测汇总
    """
    if not predictions:
        return "暂无预测"

    lines = ["📊 *AI 预测汇总:*"]

    # 统计预测结果分布
    # 支持两种格式：home/draw/away 或 home_win/draw/away_win
    result_counts = {"home": 0, "draw": 0, "away": 0}
    for pred in predictions:
        result = pred.get("predicted_result", "")
        # 标准化结果格式
        if result in ("home_win", "home"):
            result_counts["home"] += 1
        elif result in ("draw",):
            result_counts["draw"] += 1
        elif result in ("away_win", "away"):
            result_counts["away"] += 1

    total = sum(result_counts.values())
    if total > 0:
        lines.append(f"• 主胜: {result_counts['home']} 票 ({result_counts['home']*100//total}%)")
        lines.append(f"• 平局: {result_counts['draw']} 票 ({result_counts['draw']*100//total}%)")
        lines.append(f"• 客胜: {result_counts['away']} 票 ({result_counts['away']*100//total}%)")

    # 各模型预测详情（最多显示前 5 个）
    lines.append("")
    lines.append("*各模型预测:*")
    for pred in predictions[:5]:
        model_name = pred.get("model_name", "未知")
        home_score = pred.get("predicted_home_score", "?")
        away_score = pred.get("predicted_away_score", "?")
        confidence = pred.get("confidence", 0)

        confidence_bar = "🟢" if confidence >= 70 else "🟡" if confidence >= 50 else "🔴"
        lines.append(f"• {model_name}: {home_score}-{away_score} {confidence_bar}{confidence}%")

    if len(predictions) > 5:
        lines.append(f"...还有 {len(predictions) - 5} 个模型")

    return "\n".join(lines)


def format_daily_summary(
    matches: list[dict],
    predictions: dict[int, list[dict]],
    date_str: str,
) -> str:
    """格式化每日比赛摘要

    Args:
        matches: 今日比赛列表
        predictions: 比赛 ID -> 预测列表的映射
        date_str: 日期字符串

    Returns:
        str: 格式化的每日摘要消息
    """
    lines = [
        f"📅 *{date_str} 比赛预测*",
        f"共 {len(matches)} 场比赛",
        "",
    ]

    if not matches:
        lines.append("今日暂无比赛安排")
        return "\n".join(lines)

    # 按联赛分组
    matches_by_league: dict[str, list[dict]] = {}
    for match in matches:
        league = match.get("league_name", "其他联赛")
        if league not in matches_by_league:
            matches_by_league[league] = []
        matches_by_league[league].append(match)

    for league, league_matches in matches_by_league.items():
        lines.append(f"🏆 *{league}*")
        lines.append("─" * 20)

        for match in league_matches:
            match_id = match.get("id")
            home_team = match.get("home_team", "未知")
            away_team = match.get("away_team", "未知")
            match_time = match.get("match_time", "")

            # 格式化时间
            time_str = ""
            if match_time:
                try:
                    if isinstance(match_time, str):
                        dt = datetime.fromisoformat(match_time.replace("Z", "+00:00"))
                    else:
                        dt = match_time
                    cn_tz = timezone(timedelta(hours=8))
                    dt_cn = dt.astimezone(cn_tz)
                    time_str = dt_cn.strftime("%H:%M")
                except Exception:
                    time_str = ""

            lines.append(f"\n⏰ {time_str} | *{home_team}* vs *{away_team}*")

            # 添加预测汇总
            if match_id in predictions:
                preds = predictions[match_id]
                if preds:
                    # 简化显示：只显示共识结果
                    result_counts = {"home": 0, "draw": 0, "away": 0}
                    score_counts: dict[str, int] = {}
                    for pred in preds:
                        result = pred.get("predicted_result", "")
                        # 标准化结果格式
                        if result in ("home_win", "home"):
                            result_counts["home"] += 1
                        elif result in ("draw",):
                            result_counts["draw"] += 1
                        elif result in ("away_win", "away"):
                            result_counts["away"] += 1
                        score = f"{pred.get('predicted_home_score', '?')}-{pred.get('predicted_away_score', '?')}"
                        score_counts[score] = score_counts.get(score, 0) + 1

                    # 共识结果
                    consensus = max(result_counts, key=result_counts.get)
                    consensus_emoji = {"home": "🏠", "draw": "🤝", "away": "✈️"}.get(consensus, "")
                    consensus_label = {"home": "主胜", "draw": "平局", "away": "客胜"}.get(consensus, "")

                    # 热门比分
                    if score_counts:
                        hot_score = max(score_counts, key=score_counts.get)
                        lines.append(
                            f"  {consensus_emoji} 共识: *{consensus_label}* | "
                            f"热门比分: {hot_score} ({score_counts[hot_score]}票)"
                        )
                    else:
                        lines.append(f"  {consensus_emoji} 共识: *{consensus_label}*")

    # 底部提示
    lines.append("")
    lines.append("─" * 20)
    lines.append("💡 _使用 /predict 查看详细预测_")

    return "\n".join(lines)


def format_finished_matches_summary(matches: list[dict]) -> str:
    """格式化已结束比赛摘要（昨日赛果）

    Args:
        matches: 已结束比赛列表

    Returns:
        str: 格式化的昨日赛果消息
    """
    if not matches:
        return "📋 *昨日无已结束比赛*"

    lines = [
        "📋 *昨日赛果*",
        f"共 {len(matches)} 场比赛",
        "",
    ]

    # 按联赛分组
    matches_by_league: dict[str, list[dict]] = {}
    for match in matches:
        league = match.get("league_name", "其他联赛")
        if league not in matches_by_league:
            matches_by_league[league] = []
        matches_by_league[league].append(match)

    for league, league_matches in matches_by_league.items():
        lines.append(f"🏆 *{league}*")

        for match in league_matches:
            home_team = match.get("home_team", "未知")
            away_team = match.get("away_team", "未知")
            home_score = match.get("home_score", "?")
            away_score = match.get("away_score", "?")

            lines.append(f"• {home_team} *{home_score}* - *{away_score}* {away_team}")

        lines.append("")

    return "\n".join(lines)


def format_leaderboard_update(ai_leaderboard: list[dict], top_n: int = 5) -> str:
    """格式化排行榜更新

    Args:
        ai_leaderboard: AI 排行榜数据
        top_n: 显示前 N 名

    Returns:
        str: 格式化的排行榜消息
    """
    if not ai_leaderboard:
        return "📊 *AI 排行榜*\n暂无数据"

    lines = [
        "📊 *AI 模型排行榜 TOP {0}*".format(top_n),
        "",
    ]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    for i, model in enumerate(ai_leaderboard[:top_n]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = model.get("model_name", "未知")
        accuracy = model.get("result_accuracy", 0)
        score_accuracy = model.get("score_accuracy", 0)

        lines.append(f"{medal} *{name}*")
        lines.append(f"   胜负命中: {accuracy}% | 比分命中: {score_accuracy}%")

    return "\n".join(lines)


def format_error_message(error: str) -> str:
    """格式化错误消息

    Args:
        error: 错误信息

    Returns:
        str: 格式化的错误消息
    """
    return (
        "⚠️ *推送服务异常*\n"
        f"错误信息: {error}\n\n"
        "_请检查服务状态或联系管理员_"
    )
