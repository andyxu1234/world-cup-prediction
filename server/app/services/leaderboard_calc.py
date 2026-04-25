"""排行榜计算服务"""

from __future__ import annotations

from sqlalchemy import select, func, case
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.prediction import Prediction
from app.models.ai_model import AIModel
from app.models.user_vote import UserVote
from app.core.cache import cached, leaderboard_cache


def _clean_avatar_url(url: str | None) -> str | None:
    """清洗无效的头像 URL（微信临时路径、非 http 等），返回 None 表示无效"""
    if not url or not url.strip():
        return None
    url = url.strip()
    # 微信临时文件路径
    if "/tmp/" in url.lower() or "http://tmp/" in url.lower():
        from loguru import logger
        logger.warning(f"[Avatar] 清洗临时URL: {url[:60]}... -> None")
        return None
    # 必须是合法 http(s) URL
    if not url.startswith("http"):
        return None
    return url


@cached(leaderboard_cache, key_fn=lambda db, round_filter="全部", sort_by="result_accuracy", sort_order="desc": f"ai_leaderboard:{round_filter}:{sort_by}:{sort_order}")
async def get_ai_leaderboard(
    db: AsyncSession,
    round_filter: str = "全部",
    sort_by: str = "result_accuracy",
    sort_order: str = "desc",
) -> list[dict]:
    """AI 模型排行榜

    Args:
        db: 数据库会话
        round_filter: 轮次筛选（全部/小组赛/淘汰赛）
        sort_by: 排序字段（result_accuracy / score_accuracy）
        sort_order: 排序方向（asc / desc）
    """
    from app.models.match import Match

    # 安全校验
    if sort_by not in ("result_accuracy", "score_accuracy"):
        sort_by = "result_accuracy"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    # 基础查询：按模型聚合
    query = (
        select(
            AIModel.id,
            AIModel.name,
            AIModel.avatar_url,
            AIModel.style_tags,
            func.count(Prediction.id).label("total"),
            func.sum(case((Prediction.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((Prediction.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .join(Prediction, Prediction.model_id == AIModel.id)
        .join(Match, Match.id == Prediction.match_id)
        .where(Prediction.is_correct_result.isnot(None))
    )

    if round_filter and round_filter != "全部":
        rounds = [r.strip() for r in round_filter.split(",") if r.strip()]
        if len(rounds) == 1:
            query = query.where(Match.round == rounds[0])
        elif len(rounds) > 1:
            query = query.where(Match.round.in_(rounds))

    # 层级排序：主排字段 → 副排字段 → 总票数
    main_col = func.sum(case((Prediction.is_correct_result == True, 1), else_=0)) / func.count(Prediction.id)
    sub_col = func.sum(case((Prediction.is_correct_score == True, 1), else_=0)) / func.count(Prediction.id)
    count_col = func.count(Prediction.id)

    # 确定主排序方向
    from sqlalchemy import asc, desc
    main_dir = desc if sort_order == "desc" else asc
    sub_dir = desc  # 副排始终降序
    count_dir = desc  # 票数始终降序

    if sort_by == "score_accuracy":
        # 主排：比分命中率 → 副排：胜负正确率 → 票数
        order_clause = sub_col, main_dir(main_col), count_dir(count_col)
    else:
        # 默认：胜负正确率 → 比分命中 → 票数
        order_clause = main_dir(main_col), sub_dir(sub_col), count_dir(count_col)

    query = query.group_by(AIModel.id).order_by(*order_clause)

    result = await db.execute(query)
    rows = result.all()

    leaderboard = []
    for row in rows:
        total = row.total or 0
        correct_result = row.correct_result or 0
        correct_score = row.correct_score or 0
        leaderboard.append({
            "model_id": row.id,
            "name": row.name,
            "avatar_url": row.avatar_url,
            "style_tags": row.style_tags,
            "total": total,
            "correct_result": correct_result,
            "result_accuracy": round(correct_result / total * 100, 1) if total > 0 else 0,
            "correct_score": correct_score,
            "score_accuracy": round(correct_score / total * 100, 1) if total > 0 else 0,
        })

    return leaderboard


@cached(leaderboard_cache, key_fn=lambda db, current_user_id=None, round_filter="全部": f"human_leaderboard:{current_user_id or 'none'}:{round_filter}")
async def get_human_leaderboard(db: AsyncSession, current_user_id: int | None = None, round_filter: str = "全部") -> dict:
    """人机排行榜：用户群体 vs 各 AI + 人类 Top 用户排行"""
    from app.models.user import User
    from app.models.match import Match

    # 用户群体统计
    vote_stats = (
        select(
            func.count(UserVote.id).label("total"),
            func.sum(case((UserVote.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((UserVote.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .join(Match, Match.id == UserVote.match_id)
        .where(UserVote.is_correct_result.isnot(None))
    )
    if round_filter and round_filter != "全部":
        rounds = [r.strip() for r in round_filter.split(",") if r.strip()]
        if len(rounds) == 1:
            vote_stats = vote_stats.where(Match.round == rounds[0])
        elif len(rounds) > 1:
            vote_stats = vote_stats.where(Match.round.in_(rounds))
    vote_result = await db.execute(vote_stats)
    vote_row = vote_result.one()

    total = vote_row.total or 0
    correct_result = vote_row.correct_result or 0
    correct_score = vote_row.correct_score or 0

    human = {
        "name": "人类代表队",
        "total": total,
        "correct_result": correct_result,
        "result_accuracy": round(correct_result / total * 100, 1) if total > 0 else 0,
        "correct_score": correct_score,
        "score_accuracy": round(correct_score / total * 100, 1) if total > 0 else 0,
    }

    # 人类 Top 用户排行（取 Top50，前端内存排序截取 Top10）
    user_query = (
        select(
            User.id.label("user_id"),
            User.nickname,
            User.avatar_url,
            func.count(UserVote.id).label("total"),
            func.sum(case((UserVote.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((UserVote.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .join(UserVote, UserVote.user_id == User.id)
        .join(Match, Match.id == UserVote.match_id)
        .where(UserVote.is_correct_result.isnot(None))
    )
    if round_filter and round_filter != "全部":
        rounds = [r.strip() for r in round_filter.split(",") if r.strip()]
        if len(rounds) == 1:
            user_query = user_query.where(Match.round == rounds[0])
        elif len(rounds) > 1:
            user_query = user_query.where(Match.round.in_(rounds))
    user_query = user_query.group_by(User.id).order_by(
        (func.sum(case((UserVote.is_correct_result == True, 1), else_=0)) / func.count(UserVote.id)).desc(),
        (func.sum(case((UserVote.is_correct_score == True, 1), else_=0)) / func.count(UserVote.id)).desc(),
        func.count(UserVote.id).desc(),
    ).limit(50)
    user_result = await db.execute(user_query)
    user_rows = user_result.all()

    user_ranking = []
    for row in user_rows:
        utotal = row.total or 0
        ucr = row.correct_result or 0
        ucs = row.correct_score or 0
        user_ranking.append({
            "user_id": row.user_id,
            "nickname": row.nickname or "匿名用户",
            "avatar_url": _clean_avatar_url(row.avatar_url),
            "total": utotal,
            "correct_result": ucr,
            "result_accuracy": round(ucr / utotal * 100, 1) if utotal > 0 else 0,
            "correct_score": ucs,
            "score_accuracy": round(ucs / utotal * 100, 1) if utotal > 0 else 0,
        })

    # 当前用户排名（如果在 Top50 中则直接取，否则单独查）
    my_rank = None
    if current_user_id:
        ranked_ids = {u["user_id"] for u in user_ranking}
        if current_user_id in ranked_ids:
            my_rank = next(u for u in user_ranking if u["user_id"] == current_user_id)
        else:
            # 单独查当前用户数据
            my_query = (
                select(
                    User.id.label("user_id"),
                    User.nickname,
                    User.avatar_url,
                    func.count(UserVote.id).label("total"),
                    func.sum(case((UserVote.is_correct_result == True, 1), else_=0)).label("correct_result"),
                    func.sum(case((UserVote.is_correct_score == True, 1), else_=0)).label("correct_score"),
                )
                .outerjoin(UserVote, UserVote.user_id == User.id)
                .where(User.id == current_user_id)
                .group_by(User.id)
            )
            my_result = await db.execute(my_query)
            my_row = my_result.one_or_none()
            if my_row and my_row.total and my_row.total > 0:
                utotal = my_row.total or 0
                ucr = my_row.correct_result or 0
                ucs = my_row.correct_score or 0
                my_rank = {
                    "user_id": my_row.user_id,
                    "nickname": my_row.nickname or "我",
                    "avatar_url": _clean_avatar_url(my_row.avatar_url),
                    "total": utotal,
                    "correct_result": ucr,
                    "result_accuracy": round(ucr / utotal * 100, 1) if utotal > 0 else 0,
                    "correct_score": ucs,
                    "score_accuracy": round(ucs / utotal * 100, 1) if utotal > 0 else 0,
                }
        # 计算全局排名：胜率更高或胜率相同比分更高的用户数 + 1
        if my_rank:
            rank_val = (
                sum(1 for u in user_ranking
                    if u["result_accuracy"] > my_rank["result_accuracy"]
                    or (u["result_accuracy"] == my_rank["result_accuracy"]
                        and u["score_accuracy"] > my_rank["score_accuracy"])
                    or (u["result_accuracy"] == my_rank["result_accuracy"]
                        and u["score_accuracy"] == my_rank["score_accuracy"]
                        and u["total"] > my_rank["total"]))
                + 1
            )
            my_rank["_rank"] = rank_val

    # AI 模型统计（使用相同的 round_filter）
    ai_leaderboard = await get_ai_leaderboard(db, round_filter=round_filter)

    return {
        "human": human,
        "ai_models": ai_leaderboard,
        "top_users": user_ranking,
        "my_rank": my_rank,
    }


@cached(leaderboard_cache, key_fn=lambda db, model_id=0: f"ai_model_detail:{model_id}")
async def get_ai_model_detail(db: AsyncSession, model_id: int) -> dict:
    """AI 模型预测详情：模型统计 + 所有预测记录"""
    from app.models.user import User
    from app.models.match import Match

    # 获取模型信息
    model_stmt = select(AIModel).where(AIModel.id == model_id)
    model_result = await db.execute(model_stmt)
    ai_model = model_result.scalar_one_or_none()
    if not ai_model:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="AI 模型不存在")

    # 模型统计（所有已出结果的预测）
    pred_stats = (
        select(
            func.count(Prediction.id).label("total"),
            func.sum(case((Prediction.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((Prediction.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .where(Prediction.model_id == model_id)
        .where(Prediction.is_correct_result.isnot(None))
    )
    stats_row = (await db.execute(pred_stats)).one()
    total = stats_row.total or 0
    correct_result = stats_row.correct_result or 0
    correct_score = stats_row.correct_score or 0

    # 查询该模型的所有预测记录（带比赛详情）
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    pred_list_stmt = (
        select(Prediction, Match, HomeTeam, AwayTeam)
        .join(Match, Match.id == Prediction.match_id)
        .join(HomeTeam, Match.home_team_id == HomeTeam.id)
        .join(AwayTeam, Match.away_team_id == AwayTeam.id)
        .where(Prediction.model_id == model_id)
        .order_by(Match.match_time.desc())
    )
    pred_rows = (await db.execute(pred_list_stmt)).all()

    predictions = []
    for row in pred_rows:
        pred, match, home, away = row
        predictions.append({
            "prediction_id": pred.id,
            "match_id": pred.match_id,
            "round": match.round or "",
            "match_time": match.match_time.isoformat() if match.match_time else None,
            "match_status": match.status.value if match.status else "",
            "home_team_name": home.cn_name or home.name or "",
            "home_team_flag": _clean_avatar_url(home.flag_url),
            "away_team_name": away.cn_name or away.name or "",
            "away_team_flag": _clean_avatar_url(away.flag_url),
            "match_result": match.result.value if match.result else None,
            "match_home_score": match.home_score,
            "match_away_score": match.away_score,
            "predicted_result": str(pred.result),
            "predicted_home_score": pred.score_home,
            "predicted_away_score": pred.score_away,
            "is_correct_result": pred.is_correct_result,
            "is_correct_score": pred.is_correct_score,
            "confidence": float(pred.confidence) if pred.confidence else None,
            "created_at": pred.created_at.isoformat() if pred.created_at else None,
        })

    return {
        "model_id": ai_model.id,
        "name": ai_model.name,
        "avatar_url": ai_model.avatar_url,
        "style_tags": ai_model.style_tags,
        "total_predictions": total,
        "correct_results": correct_result,
        "result_accuracy": round(correct_result / total * 100, 1) if total > 0 else 0,
        "correct_scores": correct_score,
        "score_accuracy": round(correct_score / total * 100, 1) if total > 0 else 0,
        "predictions": predictions,
    }

