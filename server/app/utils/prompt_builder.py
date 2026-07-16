"""Prompt 构建工具"""

from __future__ import annotations

from app.models.team import Team
from app.models.match import Match
from typing import Optional


SYSTEM_PROMPT = """你是一位资深足球分析专家，请根据提供的数据预测以下足球比赛的结果。

你需要综合考虑球队实力、近期状态、历史交锋、主客场表现等多维度数据，做出专业判断。

严格按照JSON格式输出，不要输出其他任何内容。"""


def _format_team_stats(team: Team) -> str:
    """格式化球队赛季统计为文本"""
    parts = [f"FIFA排名 #{team.fifa_rank or '未知'}"]

    if team.group_name:
        parts.append(f"小组 {team.group_name}")

    stats = team.season_stats
    if stats and isinstance(stats, list):
        # season_stats 是一个 list（每个联赛一条），取最近/最重要的联赛
        for league_stat in stats:
            league_name = league_stat.get("leagueName", "")
            total = league_stat.get("total", {})
            games = total.get("games", {})
            goals = total.get("goals", {})
            home = league_stat.get("home", {})
            away = league_stat.get("away", {})

            home_games = home.get("games", {})
            away_games = away.get("games", {})

            parts.append(
                f"\n    {league_name}赛季统计："
                f"{games.get('wins', '?')}胜{games.get('draws', '?')}平{games.get('loses', '?')}负，"
                f"进{goals.get('scored', '?')}球失{goals.get('received', '?')}球"
            )
            if home_games:
                parts.append(
                    f"\n    主场：{home_games.get('wins', '?')}胜{home_games.get('draws', '?')}平{home_games.get('loses', '?')}负，"
                    f"进{home.get('goals', {}).get('scored', '?')}失{home.get('goals', {}).get('received', '?')}"
                )
            if away_games:
                parts.append(
                    f"\n    客场：{away_games.get('wins', '?')}胜{away_games.get('draws', '?')}平{away_games.get('loses', '?')}负，"
                    f"进{away.get('goals', {}).get('scored', '?')}失{away.get('goals', {}).get('received', '?')}"
                )
            # 只取第一条统计
            break

    return "".join(parts)


def _format_recent_form(team: Team) -> str:
    """格式化最近5场状态为文本"""
    form = team.recent_form
    if not form or not isinstance(form, dict):
        return "暂无数据"

    matches = form.get("matches", [])
    if not matches:
        return "暂无数据"

    lines = []
    for m in matches[:5]:
        home = m.get("home", "?")
        away = m.get("away", "?")
        score = m.get("score", "-")
        date = m.get("date", "")
        # 判断该队是主还是客，标记胜负
        result_tag = ""
        if score and " - " in score:
            try:
                h_s, a_s = score.split(" - ")
                h_s, a_s = int(h_s.strip()), int(a_s.strip())
                if home == team.name:
                    result_tag = "胜" if h_s > a_s else ("平" if h_s == a_s else "负")
                else:
                    result_tag = "胜" if a_s > h_s else ("平" if a_s == h_s else "负")
            except (ValueError, IndexError):
                pass

        lines.append(f"    {date} {home} {score} {away} [{result_tag}]")

    return "\n".join(lines)


def _format_head_to_head(h2h_data: Optional[list], home_team_name: str, away_team_name: str) -> str:
    """格式化历史交锋数据为文本"""
    if not h2h_data:
        return "暂无历史交锋数据"

    lines = []
    home_wins = 0
    draws = 0
    away_wins = 0

    for m in h2h_data[:10]:
        home = m.get("home", "?")
        away = m.get("away", "?")
        score = m.get("score", "-")
        date = m.get("date", "")

        # 统计胜负（以当前主客队为视角）
        if score and " - " in score:
            try:
                h_s, a_s = score.split(" - ")
                h_s, a_s = int(h_s.strip()), int(a_s.strip())
                if home == home_team_name:
                    if h_s > a_s:
                        home_wins += 1
                    elif h_s == a_s:
                        draws += 1
                    else:
                        away_wins += 1
                else:
                    if a_s > h_s:
                        home_wins += 1
                    elif h_s == a_s:
                        draws += 1
                    else:
                        away_wins += 1
            except (ValueError, IndexError):
                pass

        lines.append(f"  {date} {home} {score} {away}")

    summary = f"\n近{len(h2h_data)}场交锋：{home_team_name} {home_wins}胜 {draws}平 {away_team_name} {away_wins}胜"

    return summary + "\n" + "\n".join(lines)


def build_user_prompt(
    home_team: Team,
    away_team: Team,
    match: Match,
    head_to_head: Optional[list] = None,
    league_name: Optional[str] = None,
) -> str:
    """构建单场预测的用户 Prompt — 包含丰富数据"""
    h2h_text = _format_head_to_head(head_to_head, home_team.name, away_team.name)

    return f"""比赛信息：
- 比赛：{home_team.name} vs {away_team.name}
- 联赛：{league_name or '未知联赛'}
- 轮次：{match.round}
- 场地：{match.venue or '待定'}

球队信息：
- {home_team.name}：{_format_team_stats(home_team)}
- {away_team.name}：{_format_team_stats(away_team)}

近期状态：
- {home_team.name} 近5场：
{_format_recent_form(home_team)}
- {away_team.name} 近5场：
{_format_recent_form(away_team)}

历史交锋：{h2h_text}

请综合以上数据，严格按照以下JSON格式输出预测结果，不要输出其他内容：
{{
  "result": "home_win|draw|away_win",
  "score": {{ "home": 0, "away": 0 }},
  "score_alt": {{ "home": 0, "away": 0, "probability": 0.0 }},
  "confidence": 5,
  "analysis": "80-200字的预测分析，需结合上述数据说明判断依据"
}}"""


def build_summary_prompt(
    home_team: str,
    away_team: str,
    predictions: list[dict],
    league_name: Optional[str] = None,
) -> str:
    """构建汇总预测的 Prompt：综合多个 AI 模型的预测结果，生成统一结论"""
    pred_lines = []
    for p in predictions:
        model_name = p.get("model_name", "AI")
        result = p.get("result", "?")
        score_h = p.get("score_home", "?")
        score_a = p.get("score_away", "?")
        confidence = p.get("confidence", "-")
        analysis = p.get("analysis", "")
        result_cn = {"home_win": "主胜", "draw": "平局", "away_win": "客胜"}.get(result, result)
        pred_lines.append(
            f"  - {model_name}：预测{result_cn}，比分 {score_h}:{score_a}，信心 {confidence}/10\n    分析：{analysis}"
        )

    preds_text = "\n".join(pred_lines)

    return f"""你是足球分析总编辑，请综合以下多个AI模型对同一场比赛的预测，生成统一的综合预测结论。

比赛（{league_name or '未知联赛'}）：{home_team} vs {away_team}

各AI模型预测：
{preds_text}

请综合权衡各模型的观点（信心高的权重更大），严格按照以下JSON格式输出，不要输出其他内容：
{{
  "result": "home_win|draw|away_win",
  "score": {{ "home": 0, "away": 0 }},
  "score_alt": {{ "home": 0, "away": 0, "probability": 0.0 }},
  "confidence": 5,
  "short_summary": "10字以内的简短结论，如'主队小胜'、'势均力敌'",
  "summary": "100-200字的综合分析，需说明各模型共识与分歧，以及最终判断依据"
}}"""


def build_long_term_prompt(teams: list[Team], league_name: Optional[str] = None) -> str:
    """构建长期预测（冠亚季军）的 Prompt"""
    team_list = "\n".join(
        f"- {t.name}（{_format_team_stats(t)}）"
        for t in teams
    )
    return f"""你是一位足球分析专家，请预测{league_name or '2026年世界杯'}的最终结果。

参赛球队：
{team_list}

请严格按照以下JSON格式输出预测结果，不要输出其他内容：
{{
  "champion": "球队名称",
  "runner_up": "球队名称",
  "third_place": "球队名称",
  "analysis": "100-200字的分析"
}}"""
