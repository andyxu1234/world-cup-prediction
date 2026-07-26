"""Prompt 构建工具"""

from __future__ import annotations

from app.models.team import Team
from app.models.match import Match
from typing import Optional



SYSTEM_PROMPT = """你是一位资深足球分析专家，请根据提供的数据预测以下足球比赛的结果。

你需要综合考虑球队实力、近期状态、历史交锋、主客场表现等多维度数据，做出专业判断。

严格按照JSON格式输出，不要输出其他任何内容。"""


def _match_league(entry: dict, league_name: Optional[str], league_highlightly_id: Optional[int]) -> bool:
    """判断 season_stats 中的一条是否属于「当前联赛」"""
    eid = entry.get("leagueId") or entry.get("league_id")
    ename = entry.get("leagueName") or entry.get("league") or ""
    # 优先用 Highlightly 联赛 ID 精确匹配
    if league_highlightly_id is not None and eid is not None:
        try:
            if int(eid) == int(league_highlightly_id):
                return True
        except (ValueError, TypeError):
            pass
    # 退化为名称模糊匹配（注意中文名 vs 英文联赛名可能不一致）
    if league_name and ename:
        return league_name in ename or ename in league_name
    return False


def _format_team_stats(
    team: Team,
    league_name: Optional[str] = None,
    league_highlightly_id: Optional[int] = None,
    league_season: Optional[int] = None,
) -> str:
    """格式化球队赛季统计为文本。

    取「当前联赛」的赛季统计；若该联赛有多赛季(当前+上赛季)则都纳入，
    而非旧逻辑只取列表第一条(可能取到友谊赛等非主赛事)。
    """
    parts = [f"FIFA排名 #{team.fifa_rank or '未知'}"]

    if team.group_name:
        parts.append(f"小组 {team.group_name}")

    stats = team.season_stats
    if not stats or not isinstance(stats, list):
        return "".join(parts)

    def _season_of(s: dict) -> Optional[int]:
        sv = s.get("season") or s.get("seasonName") or s.get("year")
        try:
            return int(str(sv))
        except (TypeError, ValueError):
            return None

    # 1) 按当前联赛过滤
    candidates = [s for s in stats if _match_league(s, league_name, league_highlightly_id)]

    # 2) 候选含赛季字段且已知当前赛季 → 仅保留 当前赛季 + 上赛季
    if candidates and league_season is not None and any(_season_of(s) is not None for s in candidates):
        kept = [s for s in candidates if _season_of(s) in (league_season, league_season - 1)]
        if kept:
            candidates = kept

    # 3) 仍无候选 → 退化为「总场次最多」的一条，避免把友谊赛等全量灌入
    if not candidates:
        def _total_games(s: dict) -> int:
            g = s.get("total", {}).get("games", {})
            return (g.get("wins", 0) or 0) + (g.get("draws", 0) or 0) + (g.get("loses", 0) or 0)
        candidates = [max(stats, key=_total_games)]

    # 4) 按赛季倒序输出（当前赛季在前）
    candidates = sorted(candidates, key=lambda s: (_season_of(s) or 0), reverse=True)

    for league_stat in candidates:
        lname = league_stat.get("leagueName") or league_stat.get("league") or ""
        season_s = league_stat.get("season") or league_stat.get("seasonName") or ""
        total = league_stat.get("total", {})
        games = total.get("games", {})
        goals = total.get("goals", {})
        home = league_stat.get("home", {})
        away = league_stat.get("away", {})
        home_games = home.get("games", {})
        away_games = away.get("games", {})

        head = f"\n    {lname}赛季统计"
        if season_s:
            head += f"（{season_s}赛季）"
        head += "："
        parts.append(
            head +
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

    return "".join(parts)


def _normalize_outcome(value: str) -> Optional[str]:
    """把赔率选项 value 归一化为 home/draw/away"""
    v = (value or "").strip().lower()
    if v in ("home", "1", "h", "win"):
        return "home"
    if v in ("draw", "x", "d"):
        return "draw"
    if v in ("away", "2", "a"):
        return "away"
    return None


# bet365 在 Highlightly 的博彩公司 ID（predict_prompt 只用这家的最新赔率）
BET365_ID = 319


def _format_odds(match_odds_rows) -> str:
    """把比赛赔率(仅 bet365 最新快照的 1X2)格式化为提示词文本。

    简化版：直接取数据库里 bet365（bookmaker_id={BET365_ID}）最新快照的
    胜平负(Full Time Result)赔率，不再做多家均值 / 隐含概率 / 赔率变动趋势。
    """.format(BET365_ID=BET365_ID)
    if not match_odds_rows:
        return ""

    # 1) 仅保留 bet365 的赛前胜平负(Full Time Result)市场
    rows = [
        o for o in match_odds_rows
        if getattr(o, "bookmaker_id", None) == BET365_ID
        and "prematch" in str(getattr(o, "odds_type", "")).lower()
        and getattr(o, "market", "") == "Full Time Result"
    ]
    if not rows:
        return ""

    # 2) 取最新快照（按 日期+小时桶，避免同日期多小时桶时取到错误值）
    latest = max((o.snapshot_date, o.snapshot_hour) for o in rows)
    latest_rows = [o for o in rows if (o.snapshot_date, o.snapshot_hour) == latest]

    label = {"home": "主胜", "draw": "平局", "away": "客胜"}
    parts = [f"bet365 最新赔率（快照 {latest[0]} {latest[1]:02d}:00）："]
    for out in ("home", "draw", "away"):
        hit = next((o for o in latest_rows if _normalize_outcome(o.value) == out), None)
        if hit is not None and hit.odd is not None:
            try:
                parts.append(f"{label[out]} {float(hit.odd):.2f}")
            except (TypeError, ValueError):
                pass

    return "\n".join(parts) if len(parts) > 1 else ""


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
    match_odds: Optional[list] = None,
) -> str:
    """构建单场预测的用户 Prompt — 包含丰富数据"""
    h2h_text = _format_head_to_head(head_to_head, home_team.name, away_team.name)

    # 联赛上下文：用于 season_stats 精准取「当前联赛」的当前/上赛季
    lg = match.league
    league_highlightly_id = lg.highlightly_league_id if lg else None
    league_season = lg.season if lg else None

    home_stats = _format_team_stats(home_team, league_name, league_highlightly_id, league_season)
    away_stats = _format_team_stats(away_team, league_name, league_highlightly_id, league_season)

    # 开赛时间
    mt = match.match_time
    if mt is not None and hasattr(mt, "strftime"):
        match_time_str = mt.strftime("%Y-%m-%d %H:%M")
    elif mt:
        match_time_str = str(mt)
    else:
        match_time_str = "待定"

    # 赔率信息（市场共识盘口 + 移动趋势）
    odds_text = _format_odds(match_odds)

    prompt = f"""比赛信息：
- 比赛：{home_team.name} vs {away_team.name}
- 赛事：{league_name or '未知赛事'}
- 轮次：{match.round}
- 场地：{match.venue or '待定'}
- 开赛时间：{match_time_str}

球队信息：
- {home_team.name}：{home_stats}
- {away_team.name}：{away_stats}

近期状态：
- {home_team.name} 近5场：
{_format_recent_form(home_team)}
- {away_team.name} 近5场：
{_format_recent_form(away_team)}

历史交锋：{h2h_text}"""

    if odds_text:
        prompt += f"""

赔率信息（bet365 最新盘口）：
{odds_text}"""

    prompt += f"""

请综合以上数据，严格按照以下JSON格式输出预测结果，不要输出其他内容：
{{
  "result": "home_win|draw|away_win",
  "score": {{ "home": 0, "away": 0 }},
  "score_alt": {{ "home": 0, "away": 0, "probability": 0.0 }},
  "confidence": 5,
  "analysis": "80-200字的预测分析，需结合上述数据说明判断依据"
}}"""
    return prompt


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

比赛（{league_name or '未知赛事'}）：{home_team} vs {away_team}

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



