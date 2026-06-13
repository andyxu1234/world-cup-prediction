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
    # 预设头像（如 preset://default_avatar）
    if url.startswith("preset://"):
        return url
    # 必须是合法 http(s) URL
    if not url.startswith("http"):
        return None
    return url


@cached(leaderboard_cache, key_fn=lambda db, round_filter="全部", sort_by="score_accuracy", sort_order="desc": f"ai_leaderboard:{round_filter}:{sort_by}:{sort_order}")
async def get_ai_leaderboard(
    db: AsyncSession,
    round_filter: str = "全部",
    sort_by: str = "score_accuracy",
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
        sort_by = "score_accuracy"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    # 基础查询：按模型聚合
    # 命中率计算：只统计已结算的预测（is_correct_result IS NOT NULL），避免未结算比赛拉低命中率
    query = (
        select(
            AIModel.id,
            AIModel.name,
            AIModel.avatar_url,
            AIModel.style_tags,
            func.count(Prediction.id).label("total"),                                    # 总预测数（所有预测）
            # 已结算预测数：is_correct_result 不为空（即比赛已结束并已评估）
            func.count(case((Prediction.is_correct_result.isnot(None), 1))).label("settled"),
            func.sum(case((Prediction.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((Prediction.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .join(Prediction, Prediction.model_id == AIModel.id)
        .join(Match, Match.id == Prediction.match_id)
    )

    if round_filter and round_filter != "全部":
        rounds = [r.strip() for r in round_filter.split(",") if r.strip()]
        if len(rounds) == 1:
            query = query.where(Match.round == rounds[0])
        elif len(rounds) > 1:
            query = query.where(Match.round.in_(rounds))

    # 层级排序：主排字段 → 副排字段 → 总票数（基于已结算数据计算命中率）
    main_col = func.sum(case((Prediction.is_correct_result == True, 1), else_=0)) / func.count(case((Prediction.is_correct_result.isnot(None), 1)))
    sub_col = func.sum(case((Prediction.is_correct_score == True, 1), else_=0)) / func.count(case((Prediction.is_correct_result.isnot(None), 1)))
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
        settled = row.settled or 0
        correct_result = row.correct_result or 0
        correct_score = row.correct_score or 0
        leaderboard.append({
            "model_id": row.id,
            "name": row.name,
            "avatar_url": row.avatar_url,
            "style_tags": row.style_tags,
            "total": total,                          # 总预测场次
            "settled": settled,                        # 已结算（已结束）场次
            "correct_result": correct_result,
            "result_accuracy": round(correct_result / settled * 100, 1) if settled > 0 else 0,
            "correct_score": correct_score,
            "score_accuracy": round(correct_score / settled * 100, 1) if settled > 0 else 0,
        })

    return leaderboard


@cached(leaderboard_cache, key_fn=lambda db, current_user_id=None, round_filter="全部": f"human_leaderboard:{current_user_id or 'none'}:{round_filter}")
async def get_human_leaderboard(db: AsyncSession, current_user_id: int | None = None, round_filter: str = "全部") -> dict:
    """人类排行榜：只从 user_votes 表查询，返回所有用户数据"""
    from app.models.user import User
    from app.models.match import Match

    # 人类用户排行（不过滤 is_correct_result，返回所有用户）
    user_query = (
        select(
            User.id.label("user_id"),
            User.nickname,
            User.avatar_url,
            func.count(UserVote.id).label("total"),
            func.count(case((UserVote.is_correct_result.isnot(None), 1))).label("settled"),
            func.sum(case((UserVote.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((UserVote.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .join(UserVote, UserVote.user_id == User.id)
        .join(Match, Match.id == UserVote.match_id)
    )
    if round_filter and round_filter != "全部":
        rounds = [r.strip() for r in round_filter.split(",") if r.strip()]
        if len(rounds) == 1:
            user_query = user_query.where(Match.round == rounds[0])
        elif len(rounds) > 1:
            user_query = user_query.where(Match.round.in_(rounds))

    # 排序：胜负命中率 DESC → 比分命中率 DESC → 投票场次 DESC → 用户ID ASC（命中率基于已结算场次）
    user_query = user_query.group_by(User.id).order_by(
        (func.sum(case((UserVote.is_correct_result == True, 1), else_=0)) / func.count(case((UserVote.is_correct_result.isnot(None), 1)))).desc(),
        (func.sum(case((UserVote.is_correct_score == True, 1), else_=0)) / func.count(case((UserVote.is_correct_result.isnot(None), 1)))).desc(),
        func.count(UserVote.id).desc(),
        User.id.asc(),
    ).limit(100)
    user_result = await db.execute(user_query)
    user_rows = user_result.all()

    user_ranking = []
    my_rank = None
    current_user_in_top = False
    for idx, row in enumerate(user_rows):
        utotal = row.total or 0
        usettled = row.settled or 0
        ucr = row.correct_result or 0
        ucs = row.correct_score or 0
        real_rank = idx + 1  # 真实排名（从1开始）
        is_current = current_user_id is not None and row.user_id == current_user_id
        if is_current:
            current_user_in_top = True
        item = {
            "user_id": row.user_id,
            "nickname": row.nickname or "匿名用户",
            "avatar_url": _clean_avatar_url(row.avatar_url),
            "total": utotal,
            "settled": usettled,
            "correct_result": ucr,
            "result_accuracy": round(ucr / usettled * 100, 1) if usettled > 0 else 0,
            "correct_score": ucs,
            "score_accuracy": round(ucs / usettled * 100, 1) if usettled > 0 else 0,
            "is_me": is_current,
            "real_rank": real_rank,
        }
        user_ranking.append(item)
        if is_current:
            my_rank = item

    # 如果当前用户不在前100名，单独查询并计算排名
    if current_user_id and not current_user_in_top:
        # 查询当前用户数据
        my_query = (
            select(
                User.id.label("user_id"),
                User.nickname,
                User.avatar_url,
                func.count(UserVote.id).label("total"),
                func.count(case((UserVote.is_correct_result.isnot(None), 1))).label("settled"),
                func.sum(case((UserVote.is_correct_result == True, 1), else_=0)).label("correct_result"),
                func.sum(case((UserVote.is_correct_score == True, 1), else_=0)).label("correct_score"),
            )
            .join(UserVote, UserVote.user_id == User.id)
            .join(Match, Match.id == UserVote.match_id)
            .where(User.id == current_user_id)
        )
        if round_filter and round_filter != "全部":
            rounds = [r.strip() for r in round_filter.split(",") if r.strip()]
            if len(rounds) == 1:
                my_query = my_query.where(Match.round == rounds[0])
            elif len(rounds) > 1:
                my_query = my_query.where(Match.round.in_(rounds))
        my_query = my_query.group_by(User.id)
        my_result = await db.execute(my_query)
        my_row = my_result.one_or_none()

        if my_row and my_row.total and my_row.total > 0:
            utotal = my_row.total or 0
            usettled = my_row.settled or 0
            ucr = my_row.correct_result or 0
            ucs = my_row.correct_score or 0
            # 计算真实排名：比当前用户成绩好的人数 + 1
            rank_sub = (
                select(
                    User.id,
                    (func.sum(case((UserVote.is_correct_result == True, 1), else_=0)) / func.count(case((UserVote.is_correct_result.isnot(None), 1)))).label("ra"),
                    (func.sum(case((UserVote.is_correct_score == True, 1), else_=0)) / func.count(case((UserVote.is_correct_result.isnot(None), 1)))).label("sa"),
                    func.count(UserVote.id).label("cnt"),
                )
                .join(UserVote, UserVote.user_id == User.id)
                .join(Match, Match.id == UserVote.match_id)
                .group_by(User.id)
            )
            rank_result = await db.execute(rank_sub)
            all_users = rank_result.all()
            my_ra = ucr / usettled if usettled > 0 else 0
            my_sa = ucs / usettled if usettled > 0 else 0
            real_rank = 1
            for u in all_users:
                u_ra = (u.ra or 0)
                u_sa = (u.sa or 0)
                u_cnt = u.cnt or 0
                if u_ra > my_ra or (u_ra == my_ra and u_sa > my_sa) or (u_ra == my_ra and u_sa == my_sa and u_cnt > utotal):
                    real_rank += 1

            my_rank = {
                "user_id": my_row.user_id,
                "nickname": my_row.nickname or "我",
                "avatar_url": _clean_avatar_url(my_row.avatar_url),
                "total": utotal,
                "settled": usettled,
                "correct_result": ucr,
                "result_accuracy": round(ucr / usettled * 100, 1) if usettled > 0 else 0,
                "correct_score": ucs,
                "score_accuracy": round(ucs / usettled * 100, 1) if usettled > 0 else 0,
                "is_me": True,
                "real_rank": real_rank,
            }
            user_ranking.insert(0, my_rank)

    # 如果当前用户在列表中，将其置顶（保留真实排名）
    elif my_rank and current_user_id:
        user_ranking.remove(my_rank)
        user_ranking.insert(0, my_rank)

    return {
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

    # 模型统计（命中率基于已结算场次）
    pred_stats = (
        select(
            func.count(Prediction.id).label("total"),
            func.count(case((Prediction.is_correct_result.isnot(None), 1))).label("settled"),
            func.sum(case((Prediction.is_correct_result == True, 1), else_=0)).label("correct_result"),
            func.sum(case((Prediction.is_correct_score == True, 1), else_=0)).label("correct_score"),
        )
        .where(Prediction.model_id == model_id)
    )
    stats_row = (await db.execute(pred_stats)).one()
    total = stats_row.total or 0
    settled = stats_row.settled or 0
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
            "score_alt_home": pred.score_alt_home,
            "score_alt_away": pred.score_alt_away,
            "score_alt_prob": float(pred.score_alt_prob) if pred.score_alt_prob else None,
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
        "settled_predictions": settled,
        "correct_results": correct_result,
        "result_accuracy": round(correct_result / settled * 100, 1) if settled > 0 else 0,
        "correct_scores": correct_score,
        "score_accuracy": round(correct_score / settled * 100, 1) if settled > 0 else 0,
        "predictions": predictions,
    }

