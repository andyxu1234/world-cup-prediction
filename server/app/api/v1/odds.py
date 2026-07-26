"""赔率只读接口（私密展示页 /internal/odds 后端）

设计要点：
- 全部接口都需要共享令牌（require_odds_token），与小程序完全隔离，不进 client/ 目录。
- 仅读，不触发任何调度 / 写操作。
- backtest 为核心：把每个 AI 模型的胜负平预测，按指定博彩公司的赛前赔率结算，
  假设每场投注 stake 元，计算各模型累计盈亏与 ROI；并额外提供一个「AI 共识（多数投票）」
  虚拟模型参与回测。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_odds_token
from app.models.match import Match, MatchStatus
from app.models.odds import Bookmaker, MatchOdd
from app.models.prediction import Prediction
from app.models.prediction_summary import PredictionSummary
from app.models.ai_model import AIModel
from app.models.team import Team
from app.models.league import League
from app.models.polymarket_event import PolymarketEvent, PolymarketMarket

router = APIRouter(prefix="/odds", tags=["odds-private"])

DBSession = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[bool, Depends(require_odds_token)]

# AI 预测 result（home_win/draw/away_win）↔ 赔率 value（Home/Draw/Away）映射
RESULT_TO_VALUE = {"home_win": "Home", "draw": "Draw", "away_win": "Away"}
VALUE_TO_RESULT = {v: k for k, v in RESULT_TO_VALUE.items()}
FT_RESULT_MARKET = "Full Time Result"
STAKE = 100  # 每场投注金额（元）


@router.get("/leagues")
async def list_leagues(
    db: DBSession = None,
    _: TokenDep = True,
):
    """联赛下拉选项（用于私密页筛选器，支持多选时前端按 id 拼接）"""
    stmt = (
        select(League)
        .where(League.is_active == True)  # noqa: E712
        .order_by(League.sort_order, League.cn_name)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {"id": l.id, "name": l.name, "cn_name": l.cn_name, "country": l.country}
        for l in rows
    ]


@router.get("/bookmakers")
async def list_bookmakers(
    db: DBSession = None,
    _: TokenDep = True,
):
    """博彩公司下拉选项（用于私密页看板/走势筛选器，支持多选）"""
    stmt = (
        select(Bookmaker)
        .where(Bookmaker.is_active == True)  # noqa: E712
        .order_by(Bookmaker.name)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {"id": b.highlightly_bookmaker_id, "name": b.name}
        for b in rows
    ]


def _team_name(team: Optional[Team]) -> str:
    if team is None:
        return "?"
    return team.cn_name or team.name


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.min
    return datetime.min


@router.get("/matches")
async def list_odds_matches(
    league_id: Optional[str] = Query(default=None, description="联赛 id，逗号分隔可多选"),
    status: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None, description="比赛日开始日期 YYYY-MM-DD"),
    end_date: Optional[date] = Query(default=None, description="比赛日结束日期 YYYY-MM-DD"),
    sort_order: Optional[str] = Query(default="asc", description="比赛时间排序：asc 升序，desc 降序"),
    db: DBSession = None,
    _: TokenDep = True,
):
    """比赛列表，附赔率最新快照日期与条数（新鲜度）"""
    stmt = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.league))
    )
    if league_id:
        ids = [int(x) for x in league_id.split(",") if x.strip()]
        if ids:
            stmt = stmt.where(Match.league_id.in_(ids))
    if status is not None:
        stmt = stmt.where(Match.status == status)
    if start_date is not None:
        stmt = stmt.where(func.date(Match.match_time) >= start_date)
    if end_date is not None:
        stmt = stmt.where(func.date(Match.match_time) <= end_date)
    if sort_order == "desc":
        stmt = stmt.order_by(Match.match_time.desc())
    else:
        stmt = stmt.order_by(Match.match_time)
    rows = (await db.execute(stmt)).scalars().all()

    mids = [m.id for m in rows]
    agg: dict[int, dict] = {}
    if mids:
        a = (
            select(
                MatchOdd.match_id,
                func.max(MatchOdd.snapshot_date),
                func.count(),
            )
            .where(MatchOdd.match_id.in_(mids))
            .group_by(MatchOdd.match_id)
        )
        for mid, mx, cnt in (await db.execute(a)).all():
            agg[mid] = {
                "latest_snapshot": mx.isoformat() if mx else None,
                "odds_count": cnt,
            }

    # AI 预测票数聚合（主胜/平/客胜），用于列表"AI 共识"列展示
    pred_summary: dict[int, dict] = {}
    if mids:
        ps = (
            select(Prediction.match_id, Prediction.result, func.count())
            .where(Prediction.match_id.in_(mids))
            .group_by(Prediction.match_id, Prediction.result)
        )
        for mid, rval, cnt in (await db.execute(ps)).all():
            rstr = rval.value if hasattr(rval, "value") else str(rval)
            pred_summary.setdefault(mid, {"total": 0, "home_win": 0, "draw": 0, "away_win": 0})
            if rstr in pred_summary[mid]:
                pred_summary[mid][rstr] = cnt
            pred_summary[mid]["total"] += cnt

    return [
        {
            "match_id": m.id,
            "highlightly_id": m.highlightly_id,
            "match_time": m.match_time.isoformat() if isinstance(m.match_time, datetime) else str(m.match_time),
            "round": m.round,
            "home": _team_name(m.home_team),
            "away": _team_name(m.away_team),
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "result": m.result.value if m.result and hasattr(m.result, "value") else None,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "odds": agg.get(m.id),
            "predictions_summary": pred_summary.get(m.id, {"total": 0, "home_win": 0, "draw": 0, "away_win": 0}),
            "league_name": m.league.cn_name if m.league else None,
            "league_country": m.league.country if m.league else None,
        }
        for m in rows
    ]


@router.get("/match/{match_id}")
async def match_odds_board(
    match_id: int,
    bookmaker_ids: Optional[str] = Query(default=None, description="逗号分隔的博彩公司 id，如 4,319"),
    market: Optional[str] = Query(default=None, description="指定市场则只返回该市场"),
    db: DBSession = None,
    _: TokenDep = True,
):
    """某场比赛当前快照的赔率看板 + AI 预测详情"""

    # AI 预测详情（始终查询，不依赖赔率是否存在）
    pred_rows = (
        await db.execute(
            select(Prediction, AIModel.name, AIModel.avatar_url)
            .outerjoin(AIModel, AIModel.id == Prediction.model_id)
            .where(Prediction.match_id == match_id)
        )
    ).all()
    predictions_out = []
    for p, mname, mavatar in pred_rows:
        predictions_out.append({
            "model_id": p.model_id,
            "model_name": mname or f"model_{p.model_id}",
            "model_avatar": mavatar,
            "result": p.result.value if hasattr(p.result, "value") else str(p.result),
            "score_home": p.score_home,
            "score_away": p.score_away,
            "alt_score_home": p.score_alt_home,
            "alt_score_away": p.score_alt_away,
            "alt_score_prob": float(p.score_alt_prob) if p.score_alt_prob is not None else None,
            "confidence": p.confidence,
            "analysis": p.analysis,
        })

    # 赔率看板（可选，无赔率数据时返回空）
    buckets = (
        await db.execute(
            select(MatchOdd.snapshot_date, MatchOdd.snapshot_hour)
            .where(MatchOdd.match_id == match_id)
        )
    ).all()
    if not buckets:
        # 无赔率快照时仍查 summary
        summary_row = (
            await db.execute(
                select(PredictionSummary).where(PredictionSummary.match_id == match_id)
            )
        ).scalar_one_or_none()
        ps_out = None
        if summary_row:
            ps_out = {
                "score_home": summary_row.score_home,
                "score_away": summary_row.score_away,
                "score_alt_home": summary_row.score_alt_home,
                "score_alt_away": summary_row.score_alt_away,
                "summary": summary_row.summary,
                "short_summary": summary_row.short_summary,
                "confidence": summary_row.confidence,
            }
        return {
            "match_id": match_id,
            "snapshot_date": None,
            "snapshot_hour": None,
            "markets": {},
            "predictions": predictions_out,
            "prediction_summary": ps_out,
            "odds_1x2": None,
        }
    latest_date, latest_hour = max(buckets)

    stmt = select(MatchOdd).where(
        MatchOdd.match_id == match_id,
        MatchOdd.snapshot_date == latest_date,
        MatchOdd.snapshot_hour == latest_hour,
    )
    if market:
        stmt = stmt.where(MatchOdd.market == market)
    if bookmaker_ids:
        ids = [int(x) for x in bookmaker_ids.split(",") if x.strip()]
        if ids:
            stmt = stmt.where(MatchOdd.bookmaker_id.in_(ids))
    rows = (await db.execute(stmt)).scalars().all()

    markets: dict[str, dict] = {}
    for r in rows:
        markets.setdefault(r.market, {}).setdefault(r.value, {})[r.bookmaker_name] = r.odd

    # ── prediction_summaries（AI 汇总）──
    summary_row = (
        await db.execute(
            select(PredictionSummary).where(PredictionSummary.match_id == match_id)
        )
    ).scalar_one_or_none()
    prediction_summary_out = None
    if summary_row:
        prediction_summary_out = {
            "score_home": summary_row.score_home,
            "score_away": summary_row.score_away,
            "score_alt_home": summary_row.score_alt_home,
            "score_alt_away": summary_row.score_alt_away,
            "summary": summary_row.summary,
            "short_summary": summary_row.short_summary,
            "confidence": summary_row.confidence,
        }

    # ── 1X2 胜平负赔率（Full Time Result，最新快照，多公司对比）──
    ftr_odds_rows = (
        await db.execute(
            select(MatchOdd).where(
                MatchOdd.match_id == match_id,
                MatchOdd.market == FT_RESULT_MARKET,
                MatchOdd.odds_type == "prematch",
            )
        )
    ).scalars().all()

    # 取全部快照日期的 1X2 赔率（多日期对比）
    odds_1x2_out = None
    if ftr_odds_rows:
        ftr_dates = sorted({r.snapshot_date for r in ftr_odds_rows})
        snapshots = []
        for sd in ftr_dates:
            ftr_filtered = [r for r in ftr_odds_rows if r.snapshot_date == sd]
            odds_by_bookmaker: dict[str, dict] = {}
            for r in ftr_filtered:
                odds_by_bookmaker.setdefault(r.bookmaker_name, {})[r.value] = round(r.odd, 2)
            home_vals = [v.get("Home") for v in odds_by_bookmaker.values() if v.get("Home")]
            draw_vals = [v.get("Draw") for v in odds_by_bookmaker.values() if v.get("Draw")]
            away_vals = [v.get("Away") for v in odds_by_bookmaker.values() if v.get("Away")]
            snapshots.append({
                "date": sd.isoformat(),
                "avg": {
                    "Home": round(sum(home_vals) / len(home_vals), 2) if home_vals else None,
                    "Draw": round(sum(draw_vals) / len(draw_vals), 2) if draw_vals else None,
                    "Away": round(sum(away_vals) / len(away_vals), 2) if away_vals else None,
                },
                "bookmakers": odds_by_bookmaker,
            })
        odds_1x2_out = {
            "snapshots": snapshots,
            "snapshot_count": len(snapshots),
        }

    return {
        "match_id": match_id,
        "snapshot_date": latest_date.isoformat() if latest_date else None,
        "snapshot_hour": latest_hour,
        "markets": markets,
        "predictions": predictions_out,
        "prediction_summary": prediction_summary_out,
        "odds_1x2": odds_1x2_out,
    }


@router.get("/movement/{match_id}")
async def odds_movement(
    match_id: int,
    market: str = Query(..., description="市场，如 Full Time Result"),
    value: Optional[str] = Query(default=None, description="选项，如 Home；不填则返回该市场全部选项"),
    bookmaker_ids: Optional[str] = Query(default=None),
    db: DBSession = None,
    _: TokenDep = True,
):
    """指定市场/选项随 snapshot(日期+小时桶) 的逐公司走势序列"""
    stmt = select(MatchOdd).where(
        MatchOdd.match_id == match_id,
        MatchOdd.market == market,
    )
    if value:
        stmt = stmt.where(MatchOdd.value == value)
    if bookmaker_ids:
        ids = [int(x) for x in bookmaker_ids.split(",") if x.strip()]
        if ids:
            stmt = stmt.where(MatchOdd.bookmaker_id.in_(ids))
    stmt = stmt.order_by(
        MatchOdd.bookmaker_id, MatchOdd.value, MatchOdd.snapshot_date, MatchOdd.snapshot_hour
    )
    rows = (await db.execute(stmt)).scalars().all()

    series: dict[str, list] = {}
    for r in rows:
        key = f"{r.bookmaker_name} | {r.value}"
        series.setdefault(key, []).append(
            {"date": r.snapshot_date.isoformat(), "hour": r.snapshot_hour, "odd": r.odd}
        )

    return {"match_id": match_id, "market": market, "series": series}


@router.get("/backtest")
async def backtest(
    bookmaker_id: int = Query(default=4, description="结算用博彩公司 id，默认 Pinnacle(4)"),
    league_id: Optional[str] = Query(default=None, description="联赛 id，逗号分隔可多选"),
    start_date: Optional[date] = Query(default=None, description="比赛日开始日期 YYYY-MM-DD"),
    end_date: Optional[date] = Query(default=None, description="比赛日结束日期 YYYY-MM-DD"),
    strategy: str = Query(default="fixed", description="投注策略: fixed/kelly"),
    initial_bankroll: float = Query(default=10000.0, description="Kelly 策略初始本金"),
    kelly_fraction: float = Query(default=0.25, description="Kelly 比例系数，默认1/4 Kelly"),
    db: DBSession = None,
    _: TokenDep = True,
):
    """投注回测（核心）

    对每场已结束且有赛果的比赛：
    - 取每个 AI 模型预测的胜负平 → 映射到 Full Time Result 的 Home/Draw/Away；
    - 取该公司在比赛日之前最近一次 snapshot 的赔率（赛前公平价位）；
    - 盈亏 = 命中 ? (odd-1)*STAKE : -STAKE；
    - 聚合出每模型的场次/命中/命中率/总盈亏/ROI/累计盈亏序列；
    - 额外提供「AI 共识（多数投票）」虚拟模型参与回测。
    """
    # 0) 结算公司名称
    bm_name = (
        await db.execute(
            select(Bookmaker.name).where(Bookmaker.highlightly_bookmaker_id == bookmaker_id)
        )
    ).scalar()
    bookmaker_name = bm_name or f"#{bookmaker_id}"

    # 1) 已结束且有赛果的比赛（按 match_time 排序，作为累计曲线时间轴）
    stmt = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.status == MatchStatus.finished, Match.result.isnot(None))
    )
    if league_id:
        ids = [int(x) for x in league_id.split(",") if x.strip()]
        if ids:
            stmt = stmt.where(Match.league_id.in_(ids))
    if start_date is not None:
        stmt = stmt.where(func.date(Match.match_time) >= start_date)
    if end_date is not None:
        stmt = stmt.where(func.date(Match.match_time) <= end_date)
    stmt = stmt.order_by(Match.match_time)
    matches = (await db.execute(stmt)).scalars().all()
    if not matches:
        return {"bookmaker_id": bookmaker_id, "bookmaker_name": bookmaker_name, "stake": STAKE, "models": [], "details": []}

    mids = [m.id for m in matches]

    # 2) 各模型预测（LEFT JOIN，防止 ai_models 缺失导致整行丢失）
    p_stmt = (
        select(Prediction, AIModel.name, AIModel.avatar_url)
        .outerjoin(AIModel, AIModel.id == Prediction.model_id)
        .where(Prediction.match_id.in_(mids))
    )
    pred_rows = (await db.execute(p_stmt)).all()
    preds_by_match: dict[int, list] = defaultdict(list)
    all_models: dict[int, dict] = {}
    for p_row, mname, mavatar in pred_rows:
        name = mname or f"model_{p_row.model_id}"
        preds_by_match[p_row.match_id].append({
            "model_id": p_row.model_id, "name": name, "avatar": mavatar,
            "result": p_row.result, "confidence": p_row.confidence,
        })
        if p_row.model_id not in all_models:
            all_models[p_row.model_id] = {"name": name, "avatar": mavatar}

    # 3) 该公司在这些比赛的 Full Time Result 赔率
    o_stmt = select(MatchOdd).where(
        MatchOdd.match_id.in_(mids),
        MatchOdd.bookmaker_id == bookmaker_id,
        MatchOdd.market == FT_RESULT_MARKET,
    )
    odds_rows = (await db.execute(o_stmt)).scalars().all()
    odds_count = len(odds_rows)
    # (match_id, value) -> [((snapshot_date, snapshot_hour), odd)] 已排序
    odds_map: dict[tuple, list] = defaultdict(list)
    for o in odds_rows:
        odds_map[(o.match_id, o.value)].append(((o.snapshot_date, o.snapshot_hour), o.odd))
    for k in odds_map:
        odds_map[k].sort(key=lambda x: x[0])

    def get_odd(match_id: int, value: str, match_dt: datetime) -> tuple[Optional[float], bool]:
        """取赛前最近快照;若无赛前快照,则兜底使用最早可用快照(适用于历史数据赛后补抓场景)

        返回: (odd, is_fallback)
        """
        lst = odds_map.get((match_id, value))
        if not lst:
            return None, False
        match_date = match_dt.date() if isinstance(match_dt, datetime) else match_dt
        best = None
        for (sd, sh), odd in lst:
            if sd <= match_date:
                best = odd
            else:
                break
        if best is None:
            # 兜底:所有快照都在比赛日之后,使用最早那条(至少让用户能看到回测)
            return lst[0][1], True
        return best, False

    # 4) 逐场结算
    # 先初始化所有出现过的模型
    model_stats: dict = {}
    for mid, info in all_models.items():
        model_stats[mid] = {
            "name": info["name"], "avatar": info["avatar"], "matches": 0,
            "correct": 0, "profit": 0.0, "cumulative": [], "is_consensus": False,
            # Kelly 字段
            "kelly_bankroll": initial_bankroll,
            "kelly_profit": 0.0,
            "kelly_cumulative": [],
            "kelly_bets": 0,
            "kelly_peak": initial_bankroll,
            "kelly_matches": 0,
        }
    details: list = []
    settled_count = 0
    fallback_count = 0
    matches_without_predictions = 0
    matches_without_odds = 0

    for m in matches:
        has_settled_in_match = False
        m_dt = _as_datetime(m.match_time)
        m_result_val = m.result.value if hasattr(m.result, "value") else str(m.result)
        detail = {
            "match_id": m.id,
            "match_time": m_dt.isoformat() if isinstance(m_dt, datetime) else str(m_dt),
            "home": _team_name(m.home_team),
            "away": _team_name(m.away_team),
            "result": m_result_val,
            "per_model": {},
        }

        preds = preds_by_match.get(m.id, [])
        if not preds:
            matches_without_predictions += 1
        settled = []  # (name, value, odd)
        for pr in preds:
            rval = pr["result"].value if hasattr(pr["result"], "value") else str(pr["result"])
            value = RESULT_TO_VALUE.get(rval)
            odd, is_fallback = get_odd(m.id, value, m_dt) if value else (None, False)
            if odd is None:
                detail["per_model"][pr["name"]] = {
                    "pick": value, "odd": None, "correct": None,
                    "profit": None, "no_odds": True,
                }
                continue
            correct = rval == m_result_val
            profit = (odd - 1) * STAKE if correct else -STAKE
            detail["per_model"][pr["name"]] = {
                "pick": value, "odd": round(odd, 2),
                "correct": bool(correct), "profit": profit,
            }
            st = model_stats[pr["model_id"]]
            st["matches"] += 1
            if correct:
                st["correct"] += 1
            st["profit"] += profit
            st["cumulative"].append(
                {"match_id": m.id, "match_time": detail["match_time"],
                 "running": round(st["profit"], 2)}
            )

            # ── Kelly 投注计算 ──
            p_conf = pr.get("confidence")
            p_val = (p_conf / 10.0) if p_conf is not None else 0.5
            p_val = max(0.01, min(0.99, p_val))
            kelly_f = (p_val * odd - 1) / (odd - 1) if odd > 1 else 0
            kelly_f = max(0, kelly_f)
            if kelly_f > 0 and strategy in ("kelly", "both"):
                kelly_bet = round(st["kelly_bankroll"] * kelly_fraction * kelly_f, 2)
                kelly_bet = max(0, kelly_bet)
                kelly_profit = round(kelly_bet * (odd - 1), 2) if correct else -kelly_bet
                st["kelly_bankroll"] = round(st["kelly_bankroll"] + kelly_profit, 2)
                st["kelly_profit"] = round(st["kelly_profit"] + kelly_profit, 2)
                st["kelly_bets"] += 1
                if st["kelly_bankroll"] > st["kelly_peak"]:
                    st["kelly_peak"] = st["kelly_bankroll"]
                st["kelly_cumulative"].append(
                    {"match_id": m.id, "match_time": detail["match_time"],
                     "running": round(st["kelly_profit"], 2),
                     "bankroll": round(st["kelly_bankroll"], 2)}
                )
                st["kelly_matches"] += 1
                detail["per_model"][pr["name"]].update({
                    "kelly_bet": kelly_bet,
                    "kelly_profit": round(kelly_profit, 2),
                    "kelly_bankroll": round(st["kelly_bankroll"], 2),
                    "kelly_f": round(kelly_f, 4),
                })
            else:
                detail["per_model"][pr["name"]].update({
                    "kelly_bet": 0, "kelly_profit": 0,
                    "kelly_bankroll": round(st["kelly_bankroll"], 2),
                    "kelly_f": 0, "kelly_skip": kelly_f <= 0,
                })

            settled.append((pr["name"], value, odd))
            settled_count += 1
            if is_fallback:
                fallback_count += 1
            has_settled_in_match = True

        if preds and not has_settled_in_match:
            matches_without_odds += 1

        # 5) AI 共识（多数投票）虚拟模型 + 软概率 Kelly
        if settled:
            # 先计算软概率分布（与 Polymarket 分析逻辑一致）
            PRIOR_BT = {"home": 0.45, "draw": 0.27, "away": 0.28}
            RESULT_MAP_BT = {"home_win": "home", "draw": "draw", "away_win": "away"}
            VALUE_TO_OUTCOME = {"Home": "home", "Draw": "draw", "Away": "away"}
            acc_soft = {"home": 0.0, "draw": 0.0, "away": 0.0}
            n_valid_soft = 0
            for pr in preds:
                rval_pr = pr["result"].value if hasattr(pr["result"], "value") else str(pr["result"])
                rk_pr = RESULT_MAP_BT.get(rval_pr)
                if not rk_pr:
                    continue
                n_valid_soft += 1
                p_conf_pr = pr.get("confidence")
                c_pr = (p_conf_pr / 10.0) if p_conf_pr is not None else 0.5
                c_pr = max(0.0, min(1.0, c_pr))
                rem_pr = 1.0 - c_pr
                norm_pr = 1.0 - PRIOR_BT[rk_pr]
                for k in PRIOR_BT:
                    if k == rk_pr:
                        acc_soft[k] += c_pr
                    else:
                        acc_soft[k] += rem_pr * (PRIOR_BT[k] / norm_pr)

            # 多数投票（原有）
            votes: dict[str, int] = defaultdict(int)
            for _n, v, _o in settled:
                votes[v] += 1
            cons_value = max(votes, key=lambda k: votes[k])
            cons_odd, _ = get_odd(m.id, cons_value, m_dt)
            if cons_odd is not None:
                cons_correct = VALUE_TO_RESULT[cons_value] == m_result_val
                cons_profit = (cons_odd - 1) * STAKE if cons_correct else -STAKE
                detail["consensus"] = {
                    "pick": cons_value, "odd": round(cons_odd, 2),
                    "correct": bool(cons_correct), "profit": cons_profit,
                }
                cst = model_stats.setdefault(
                    "__consensus__",
                    {"name": "AI Consensus", "avatar": None, "matches": 0,
                     "correct": 0, "profit": 0.0, "cumulative": [], "is_consensus": True,
                     "kelly_bankroll": initial_bankroll, "kelly_profit": 0.0,
                     "kelly_cumulative": [], "kelly_bets": 0,
                     "kelly_peak": initial_bankroll, "kelly_matches": 0},
                )
                cst["matches"] += 1
                if cons_correct:
                    cst["correct"] += 1
                cst["profit"] += cons_profit
                cst["cumulative"].append(
                    {"match_id": m.id, "match_time": detail["match_time"],
                     "running": round(cst["profit"], 2)}
                )

                # 共识模型的 Kelly：遍历三个 outcome，选有最高正 Kelly 的投注
                if n_valid_soft and strategy in ("kelly", "both"):
                    VALUE_TO_OUTCOME = {"Home": "home", "Draw": "draw", "Away": "away"}
                    best_kelly = {"idx": None, "f": 0.0, "val": None, "odd": None, "p": 0.0}
                    for val in ("Home", "Draw", "Away"):
                        out = VALUE_TO_OUTCOME[val]
                        odd_val, _ = get_odd(m.id, val, m_dt)
                        if odd_val is None:
                            continue
                        p_val = acc_soft[out] / n_valid_soft
                        p_val = max(0.01, min(0.99, p_val))
                        kelly_f = (p_val * odd_val - 1) / (odd_val - 1) if odd_val > 1 else 0
                        if kelly_f > best_kelly["f"]:
                            best_kelly = {"idx": val, "f": kelly_f, "val": val, "odd": odd_val, "p": p_val}
                    if best_kelly["f"] > 0:
                        bk = best_kelly
                        cons_kelly_bet = round(cst["kelly_bankroll"] * kelly_fraction * bk["f"], 2)
                        cons_kelly_bet = max(0, cons_kelly_bet)
                        bk_correct = VALUE_TO_RESULT.get(bk["val"]) == m_result_val
                        cons_kelly_profit = round(cons_kelly_bet * (bk["odd"] - 1), 2) if bk_correct else -cons_kelly_bet
                        cst["kelly_bankroll"] = round(cst["kelly_bankroll"] + cons_kelly_profit, 2)
                        cst["kelly_profit"] = round(cst["kelly_profit"] + cons_kelly_profit, 2)
                        cst["kelly_bets"] += 1
                        if cst["kelly_bankroll"] > cst["kelly_peak"]:
                            cst["kelly_peak"] = cst["kelly_bankroll"]
                        cst["kelly_cumulative"].append(
                            {"match_id": m.id, "match_time": detail["match_time"],
                             "running": round(cst["kelly_profit"], 2),
                             "bankroll": round(cst["kelly_bankroll"], 2)}
                        )
                        cst["kelly_matches"] += 1
                        detail["consensus"].update({
                            "kelly_bet": cons_kelly_bet,
                            "kelly_profit": round(cons_kelly_profit, 2),
                            "kelly_bankroll": round(cst["kelly_bankroll"], 2),
                            "kelly_p": round(bk["p"], 4),
                            "kelly_pick": bk["val"],
                        })
                    else:
                        detail["consensus"].update({"kelly_bet": 0, "kelly_profit": 0,
                            "kelly_bankroll": round(cst["kelly_bankroll"], 2), "kelly_skip": True})
                else:
                    detail["consensus"].update({"kelly_bet": 0, "kelly_profit": 0,
                        "kelly_bankroll": round(cst["kelly_bankroll"], 2), "kelly_skip": True})

        details.append(detail)

    # 6) 汇总模型列表（按总盈亏降序）
    models_out = []
    for mid, st in model_stats.items():
        win_rate = round(st["correct"] / st["matches"] * 100, 1) if st["matches"] else 0
        roi = round(st["profit"] / (st["matches"] * STAKE) * 100, 2) if st["matches"] else 0
        kelly_roi = 0.0
        total_kelly_stake = 0.0
        if st.get("kelly_matches"):
            total_kelly_stake = round(sum(
                d["per_model"].get(st["name"], {}).get("kelly_bet", 0)
                for d in details
                if d["per_model"].get(st["name"], {}).get("kelly_bet", 0) > 0
            ), 2)
            kelly_roi = round(st["kelly_profit"] / total_kelly_stake * 100, 2) if total_kelly_stake else 0
        dd = 0
        if st.get("kelly_cumulative"):
            peak = st["kelly_cumulative"][0]["bankroll"]
            for pt in st["kelly_cumulative"]:
                if pt["bankroll"] > peak:
                    peak = pt["bankroll"]
                dd_val = (peak - pt["bankroll"]) / peak * 100
                if dd_val > dd:
                    dd = dd_val
        models_out.append({
            "model_id": mid,
            "name": st["name"],
            "avatar": st.get("avatar"),
            "matches": st["matches"],
            "total_stake": st["matches"] * STAKE,
            "correct": st["correct"],
            "win_rate": win_rate,
            "total_profit": round(st["profit"], 2),
            "roi": roi,
            "cumulative": st["cumulative"],
            "is_consensus": st.get("is_consensus", False),
            # Kelly
            "kelly_profit": round(st["kelly_profit"], 2),
            "kelly_cumulative": st.get("kelly_cumulative", []),
            "kelly_bets": st.get("kelly_bets", 0),
            "kelly_roi": kelly_roi,
            "kelly_total_stake": total_kelly_stake,
            "kelly_peak": round(st.get("kelly_peak", initial_bankroll), 2),
            "kelly_dd": round(dd, 1),
            "kelly_bankroll_final": round(st.get("kelly_bankroll", initial_bankroll), 2),
        })
    models_out.sort(key=lambda x: x["total_profit"], reverse=True)

    return {
        "bookmaker_id": bookmaker_id,
        "bookmaker_name": bookmaker_name,
        "stake": STAKE,
        "strategy": strategy,
        "initial_bankroll": initial_bankroll,
        "kelly_fraction": kelly_fraction,
        "models": models_out,
        "details": details,
        "diagnostics": {
            "match_count": len(matches),
            "prediction_count": len(pred_rows),
            "odds_count": odds_count,
            "settled_count": settled_count,
            "fallback_count": fallback_count,
            "matches_without_predictions": matches_without_predictions,
            "matches_without_odds": matches_without_odds,
        },
    }


# ═══════════════════════════════════════════════════════════════
#  Polymarket 关联管理（私密页 Tab 03）
# ═══════════════════════════════════════════════════════════════


@router.get("/polymarket")
async def list_polymarket_events(
    linked: Optional[str] = Query(default=None, description="筛选: 'yes'=已关联, 'no'=未关联, 不填=全部"),
    series_id: Optional[str] = Query(default=None, description="Polymarket 联赛 series_id 筛选"),
    status: Optional[str] = Query(default=None, description="按关联 Highlightly 比赛状态筛选: upcoming/live/finished"),
    sort_order: Optional[str] = Query(default="desc", description="开球时间排序：asc 升序，desc 降序"),
    db: DBSession = None,
    _: TokenDep = True,
):
    """列出所有 Polymarket 事件及其与 Highlightly 比赛的关联状态

    返回每条 PM 事件的基本信息、关联的 match_id（如有）、
    以及对应的 Highlightly 比赛信息（主客队/联赛/时间）。
    同时附带该事件下各腿（home/draw/away）的最新价格。
    """
    # 基础查询：全部 PM 事件
    if status:
        # 按关联比赛状态过滤：必须已关联且 Match.status == status
        stmt = (
            select(PolymarketEvent)
            .join(Match, PolymarketEvent.match_id == Match.id)
            .where(Match.status == status)
        )
    else:
        stmt = select(PolymarketEvent)

    if linked == "yes":
        stmt = stmt.where(PolymarketEvent.match_id.isnot(None))
    elif linked == "no":
        stmt = stmt.where(PolymarketEvent.match_id.is_(None))
    if series_id:
        stmt = stmt.where(PolymarketEvent.series_id == series_id)

    if sort_order == "asc":
        stmt = stmt.order_by(PolymarketEvent.game_start_time.asc())
    else:
        stmt = stmt.order_by(PolymarketEvent.game_start_time.desc())

    rows = (await db.execute(stmt)).scalars().all()

    # 批量取已关联的 match 信息
    linked_mids = [r.match_id for r in rows if r.match_id is not None]
    match_map: dict[int, dict] = {}
    if linked_mids:
        m_stmt = (
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.league))
            .where(Match.id.in_(linked_mids))
        )
        m_rows = (await db.execute(m_stmt)).scalars().all()
        for m in m_rows:
            match_map[m.id] = {
                "match_id": m.id,
                "home": _team_name(m.home_team),
                "away": _team_name(m.away_team),
                "league_name": m.league.cn_name if m.league else None,
                "match_time": m.match_time.isoformat() if isinstance(m.match_time, datetime) else str(m.match_time),
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            }

    # 批量取各事件的 market 价格
    event_ids = [r.id for r in rows]
    market_map: dict[int, list] = {}
    if event_ids:
        mk_stmt = (
            select(PolymarketMarket)
            .where(PolymarketMarket.event_id.in_(event_ids))
            .order_by(PolymarketMarket.outcome)
        )
        mk_rows = (await db.execute(mk_stmt)).scalars().all()
        for mk in mk_rows:
            market_map.setdefault(mk.event_id, []).append({
                "outcome": mk.outcome,
                "price": round(mk.price, 4) if mk.price is not None else None,
                "volume": round(mk.volume, 2) if mk.volume is not None else None,
                "liquidity": round(mk.liquidity, 2) if mk.liquidity is not None else None,
                "question": mk.question,
            })

    # 获取去重 series 列表（用于前端筛选项）
    all_series_stmt = (
        select(
            PolymarketEvent.series_id,
            PolymarketEvent.series_name,
            func.count().label("cnt"),
        )
        .group_by(PolymarketEvent.series_id, PolymarketEvent.series_name)
        .order_by(func.count().desc())
    )
    series_rows = (await db.execute(all_series_stmt)).all()

    result = []
    for ev in rows:
        linked_match = match_map.get(ev.match_id) if ev.match_id else None
        markets = market_map.get(ev.id, [])
        result.append({
            "id": ev.id,
            "pm_event_id": ev.pm_event_id,
            "slug": ev.slug,
            "title": ev.title,
            "series_id": ev.series_id,
            "series_name": ev.series_name,
            "home_team_raw": ev.home_team_raw,
            "away_team_raw": ev.away_team_raw,
            "game_start_time": ev.game_start_time.isoformat() if isinstance(ev.game_start_time, datetime) else str(ev.game_start_time) if ev.game_start_time else None,
            "match_id": ev.match_id,
            "linked_match": linked_match,
            "market_count": ev.market_count,
            "markets": markets,
            "last_synced_at": ev.last_synced_at.isoformat() if isinstance(ev.last_synced_at, datetime) else None,
        })

    return {
        "total": len(result),
        "series_options": [{"id": s[0], "name": s[1] or s[0], "count": s[2]} for s in series_rows],
        "events": result,
    }


@router.put("/polymarket/{event_id}/match")
async def link_polymarket_match(
    event_id: int,
    match_id: Optional[int] = Query(default=None, description="要关联的本地 match.id；传 null 或 0 解除关联"),
    highlightly_id: Optional[int] = Query(default=None, description="Highlightly 外部 match_id；后端会自动映射到本地 match.id"),
    db: DBSession = None,
    _: TokenDep = True,
):
    """手动设置/解除 Polymarket 事件与 Highlightly 比赛的关联

    - 传 match_id（本地 id）或 highlightly_id（外部 id）→ 关联（回填 polymarket_events.match_id）
    - highlightly_id 会优先解析为本地 match.id；若同时传两者，以 match_id 为准
    - 传 null / 0 / 不传 → 解除关联（置 match_id 为 NULL）
    """
    ev = (await db.execute(
        select(PolymarketEvent).where(PolymarketEvent.id == event_id)
    )).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail=f"PolymarketEvent id={event_id} not found")

    target_match_id = None
    if match_id and match_id > 0:
        target_match_id = match_id
    elif highlightly_id and highlightly_id > 0:
        # 按 Highlightly 外部 id 映射到本地 match.id
        local_id = (await db.execute(
            select(Match.id).where(Match.highlightly_id == highlightly_id)
        )).scalar_one_or_none()
        if not local_id:
            raise HTTPException(status_code=404, detail=f"Highlightly match_id={highlightly_id} not found")
        target_match_id = local_id

    if target_match_id:
        # 验证本地 match 存在
        match_exists = (await db.execute(
            select(Match.id).where(Match.id == target_match_id)
        )).scalar_one_or_none()
        if not match_exists:
            raise HTTPException(status_code=404, detail=f"Match id={target_match_id} not found")
        ev.match_id = target_match_id
    else:
        ev.match_id = None

    await db.commit()
    await db.refresh(ev)
    return {
        "status": "ok",
        "event_id": event_id,
        "match_id": ev.match_id,
        "message": f"Linked to match {ev.match_id}" if ev.match_id else "Unlinked",
    }


OUTCOME_LABELS = {"home": "主胜", "draw": "平局", "away": "客胜"}


@router.get("/polymarket/{event_id}/analysis")
async def analyze_polymarket_event(
    event_id: int,
    db: DBSession = None,
    _: TokenDep = True,
):
    """对比某 PM 事件的 AI 预测分布 vs Polymarket 市场价，计算各腿 EV / 凯利

    - 需要该事件已关联本地 match（match_id 非空）才能拿到 AI 预测分布；
      未关联时仅返回市场价 + AI 占位提示。
    - 逐腿输出 YES / NO 两侧的：价格、EV(净收益)、ROI、凯利仓位比例。
    - EV(Home YES) = AI_P(home) - price；EV(Home NO) = price - AI_P(home)。
    - 凯利 f* = EV / (赔率净收益)。
    """
    ev = (await db.execute(
        select(PolymarketEvent).where(PolymarketEvent.id == event_id)
    )).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail=f"PolymarketEvent id={event_id} not found")

    match_id = ev.match_id
    match_info = None
    ai_block = None

    if match_id is not None:
        # 关联比赛信息
        m = (await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.league))
            .where(Match.id == match_id)
        )).scalar_one_or_none()
        if m:
            match_info = {
                "match_id": m.id,
                "home": _team_name(m.home_team),
                "away": _team_name(m.away_team),
                "league_name": m.league.cn_name if m.league else None,
                "match_time": m.match_time.isoformat() if isinstance(m.match_time, datetime) else str(m.match_time),
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            }

        # AI 预测分布（按模型信心加权，避免全票=100% 的极端值）
        # 每个模型输出一个三元软概率分布：对所选结果给 confidence 概率，
        # 其余按足球先验比例分配；最后对所有模型取平均。
        # 先验（足球经验分布）：主胜 45% / 平局 27% / 客胜 28%
        PRIOR = {"home": 0.45, "draw": 0.27, "away": 0.28}
        RESULT_MAP = {"home_win": "home", "draw": "draw", "away_win": "away"}
        preds = (await db.execute(
            select(Prediction).where(Prediction.match_id == match_id)
        )).scalars().all()
        counts = {"home_win": 0, "draw": 0, "away_win": 0}
        conf_sum = 0
        acc = {"home": 0.0, "draw": 0.0, "away": 0.0}
        n_valid = 0
        for p in preds:
            r = p.result.value if hasattr(p.result, "value") else str(p.result)
            if p.confidence is not None:
                conf_sum += p.confidence
            rk = RESULT_MAP.get(r)
            if rk is None:
                continue
            counts[r] += 1
            n_valid += 1
            # confidence(0~10) -> 软概率强度 c(0~1)，缺失时按中等信心 0.5 处理
            c = (p.confidence / 10.0) if p.confidence is not None else 0.5
            c = max(0.0, min(1.0, c))
            rem = 1.0 - c
            norm = 1.0 - PRIOR[rk]
            for k in PRIOR:
                if k == rk:
                    acc[k] += c
                else:
                    acc[k] += rem * (PRIOR[k] / norm)
        total = len(preds)
        if n_valid:
            dist_pct = {k: round(acc[k] / n_valid, 4) for k in PRIOR}
        else:
            dist_pct = {k: 0.0 for k in PRIOR}
        avg_conf = round(conf_sum / total, 2) if total else None

        summ = (await db.execute(
            select(PredictionSummary).where(PredictionSummary.match_id == match_id)
        )).scalar_one_or_none()

        ai_block = {
            "total_models": total,
            "counts": {
                "home": counts["home_win"],
                "draw": counts["draw"],
                "away": counts["away_win"],
            },
            "distribution_pct": dist_pct,
            "avg_confidence": avg_conf,
            "summary": summ.summary if summ else None,
            "summary_confidence": summ.confidence if summ else None,
            "short_summary": summ.short_summary if summ else None,
        }

    # 市场价
    markets = (await db.execute(
        select(PolymarketMarket)
        .where(PolymarketMarket.event_id == event_id)
        .order_by(PolymarketMarket.outcome)
    )).scalars().all()
    price_map: dict[str, float] = {}
    market_list = []
    for mk in markets:
        price_map[mk.outcome] = mk.price
        market_list.append({
            "outcome": mk.outcome,
            "price": round(mk.price, 4) if mk.price is not None else None,
            "volume": round(mk.volume, 2) if mk.volume is not None else None,
            "liquidity": round(mk.liquidity, 2) if mk.liquidity is not None else None,
            "question": mk.question,
        })

    overround = round(sum((mk.price or 0) for mk in markets), 4)

    # 逐腿计算 YES / NO 指标
    bets = []
    best = []
    for outcome in ("home", "draw", "away"):
        price_yes = price_map.get(outcome)
        ai_prob = dist_pct.get(outcome, 0.0) if ai_block else 0.0
        if price_yes is None:
            bets.append({
                "outcome": outcome,
                "label": OUTCOME_LABELS.get(outcome, outcome),
                "ai_prob": ai_prob,
                "market_prob": None,
                "available": False,
            })
            continue
        # YES 侧
        ev_yes = round(ai_prob - price_yes, 4)
        roi_yes = round(ev_yes / price_yes, 4) if price_yes else None
        kelly_yes = round(ev_yes / (1 - price_yes), 4) if (1 - price_yes) else None
        # NO 侧
        price_no = round(1 - price_yes, 4)
        ev_no = round(price_yes - ai_prob, 4)
        roi_no = round(ev_no / price_no, 4) if price_no else None
        kelly_no = round(ev_no / price_yes, 4) if price_yes else None
        bets.append({
            "outcome": outcome,
            "label": OUTCOME_LABELS.get(outcome, outcome),
            "ai_prob": ai_prob,
            "market_prob": price_yes,
            "available": True,
            "yes": {"price": price_yes, "ev": ev_yes, "roi": roi_yes, "kelly": kelly_yes},
            "no": {"price": price_no, "ev": ev_no, "roi": roi_no, "kelly": kelly_no},
        })
        if ai_block and total:
            for side, mm in (("YES", bets[-1]["yes"]), ("NO", bets[-1]["no"])):
                if mm["ev"] is not None and mm["ev"] > 0:
                    best.append({
                        "outcome": outcome,
                        "label": OUTCOME_LABELS.get(outcome, outcome),
                        "side": side,
                        "price": mm["price"],
                        "ev": mm["ev"],
                        "roi": mm["roi"],
                        "kelly": mm["kelly"],
                    })
    best.sort(key=lambda x: x["ev"], reverse=True)

    return {
        "event": {
            "id": ev.id,
            "title": ev.title,
            "series_name": ev.series_name,
            "game_start_time": ev.game_start_time.isoformat() if isinstance(ev.game_start_time, datetime) else str(ev.game_start_time) if ev.game_start_time else None,
        },
        "match": match_info,
        "ai": ai_block,
        "markets": market_list,
        "overround": overround,
        "bets": bets,
        "best_bets": best,
        "linked": match_id is not None,
    }


@router.get("/match/{match_id}/polymarket")
async def match_polymarket_analysis(
    match_id: int,
    db: DBSession = None,
    _: TokenDep = True,
):
    """按比赛 match_id 获取关联的 Polymarket 分析数据（若已关联）

    定位到 link 到此 match 的 PM event，复用 /polymarket/{event_id}/analysis
    相同的分析逻辑返回 AI vs 市场对比数据。未关联时返回 linked=false。
    """
    ev = (await db.execute(
        select(PolymarketEvent).where(PolymarketEvent.match_id == match_id)
    )).scalar_one_or_none()

    if not ev:
        return {"linked": False, "match_id": match_id, "data": None}

    # ── 复用分析逻辑 ──────────────────────────────────
    # 关联比赛信息
    match_info = None
    ai_block = None

    m = (await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.league))
        .where(Match.id == match_id)
    )).scalar_one_or_none()
    if m:
        match_info = {
            "match_id": m.id,
            "home": _team_name(m.home_team),
            "away": _team_name(m.away_team),
            "league_name": m.league.cn_name if m.league else None,
            "match_time": m.match_time.isoformat() if isinstance(m.match_time, datetime) else str(m.match_time),
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
        }

    # AI 预测分布（信心加权软概率，与 /polymarket/{event_id}/analysis 保持一致）
    PRIOR = {"home": 0.45, "draw": 0.27, "away": 0.28}
    RESULT_MAP = {"home_win": "home", "draw": "draw", "away_win": "away"}
    preds = (await db.execute(
        select(Prediction).where(Prediction.match_id == match_id)
    )).scalars().all()
    counts = {"home_win": 0, "draw": 0, "away_win": 0}
    conf_sum = 0
    acc = {"home": 0.0, "draw": 0.0, "away": 0.0}
    n_valid = 0
    for p in preds:
        r = p.result.value if hasattr(p.result, "value") else str(p.result)
        if p.confidence is not None:
            conf_sum += p.confidence
        rk = RESULT_MAP.get(r)
        if rk is None:
            continue
        counts[r] += 1
        n_valid += 1
        c = (p.confidence / 10.0) if p.confidence is not None else 0.5
        c = max(0.0, min(1.0, c))
        rem = 1.0 - c
        norm = 1.0 - PRIOR[rk]
        for k in PRIOR:
            if k == rk:
                acc[k] += c
            else:
                acc[k] += rem * (PRIOR[k] / norm)
    total = len(preds)
    if n_valid:
        dist_pct = {k: round(acc[k] / n_valid, 4) for k in PRIOR}
    else:
        dist_pct = {k: 0.0 for k in PRIOR}
    avg_conf = round(conf_sum / total, 2) if total else None

    summ = (await db.execute(
        select(PredictionSummary).where(PredictionSummary.match_id == match_id)
    )).scalar_one_or_none()

    ai_block = {
        "total_models": total,
        "counts": {"home": counts["home_win"], "draw": counts["draw"], "away": counts["away_win"]},
        "distribution_pct": dist_pct,
        "avg_confidence": avg_conf,
        "summary": summ.summary if summ else None,
        "summary_confidence": summ.confidence if summ else None,
        "short_summary": summ.short_summary if summ else None,
    }

    # 市场价
    markets = (await db.execute(
        select(PolymarketMarket)
        .where(PolymarketMarket.event_id == ev.id)
        .order_by(PolymarketMarket.outcome)
    )).scalars().all()
    price_map: dict[str, float] = {}
    market_list = []
    for mk in markets:
        price_map[mk.outcome] = mk.price
        market_list.append({
            "outcome": mk.outcome,
            "price": round(mk.price, 4) if mk.price is not None else None,
            "volume": round(mk.volume, 2) if mk.volume is not None else None,
            "liquidity": round(mk.liquidity, 2) if mk.liquidity is not None else None,
            "question": mk.question,
        })

    overround = round(sum((mk.price or 0) for mk in markets), 4)

    # 逐腿计算 YES / NO 指标
    bets = []
    best = []
    for outcome in ("home", "draw", "away"):
        price_yes = price_map.get(outcome)
        ai_prob = dist_pct.get(outcome, 0.0) if ai_block else 0.0
        if price_yes is None:
            bets.append({
                "outcome": outcome, "label": OUTCOME_LABELS.get(outcome, outcome),
                "ai_prob": ai_prob, "market_prob": None, "available": False,
            })
            continue
        ev_yes = round(ai_prob - price_yes, 4)
        roi_yes = round(ev_yes / price_yes, 4) if price_yes else None
        kelly_yes = round(ev_yes / (1 - price_yes), 4) if (1 - price_yes) else None
        price_no = round(1 - price_yes, 4)
        ev_no = round(price_yes - ai_prob, 4)
        roi_no = round(ev_no / price_no, 4) if price_no else None
        kelly_no = round(ev_no / price_yes, 4) if price_yes else None
        bets.append({
            "outcome": outcome, "label": OUTCOME_LABELS.get(outcome, outcome),
            "ai_prob": ai_prob, "market_prob": price_yes, "available": True,
            "yes": {"price": price_yes, "ev": ev_yes, "roi": roi_yes, "kelly": kelly_yes},
            "no": {"price": price_no, "ev": ev_no, "roi": roi_no, "kelly": kelly_no},
        })
        if ai_block and total:
            for side, mm in (("YES", bets[-1]["yes"]), ("NO", bets[-1]["no"])):
                if mm["ev"] is not None and mm["ev"] > 0:
                    best.append({
                        "outcome": outcome, "label": OUTCOME_LABELS.get(outcome, outcome),
                        "side": side, "price": mm["price"],
                        "ev": mm["ev"], "roi": mm["roi"], "kelly": mm["kelly"],
                    })
    best.sort(key=lambda x: x["ev"], reverse=True)

    return {
        "linked": True,
        "match_id": match_id,
        "data": {
            "event": {
                "id": ev.id,
                "title": ev.title,
                "series_name": ev.series_name,
                "game_start_time": ev.game_start_time.isoformat() if isinstance(ev.game_start_time, datetime) else str(ev.game_start_time) if ev.game_start_time else None,
            },
            "match": match_info,
            "ai": ai_block,
            "markets": market_list,
            "overround": overround,
            "bets": bets,
            "best_bets": best,
            "linked": True,
        },
    }
