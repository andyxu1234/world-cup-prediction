"""用户相关路由"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, case
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.config import get_settings, Settings
from app.models.user import User
from app.models.user_vote import UserVote
from app.models.match import Match
from app.models.team import Team
from app.schemas.user import WechatLoginIn, UserOut, VoteIn, VoteOut, UserProfileOut, LoginOut, UpdateProfileIn
from app.schemas.vote_history import VoteHistoryItem
from app.core.wechat import WeChatClient
from app.core.auth import create_token
from app.core.cache import (
    user_profile_cache, user_votes_cache, user_vote_cache,
    get_or_set, invalidate_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/upload-avatar")
async def upload_avatar(
    user_id: int = Query(..., description="用户ID"),
    file: UploadFile = File(..., description="头像文件"),
):
    """上传头像文件，返回可访问的 URL"""
    settings: Settings = get_settings()

    # 校验文件类型
    content_type = file.content_type or ""
    if not any(t in content_type for t in ("image/jpeg", "image/png", "image/webp")) and (not file.filename or not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp 图片")

    # 生成文件名
    ext = Path(file.filename).suffix or ".jpeg"
    filename = f"u{user_id}_{uuid.uuid4().hex[:12]}{ext}"
    save_path = settings.AVATAR_SAVE_PATH / filename

    # 保存文件
    try:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="头像大小不能超过 5MB")
        save_path.write_bytes(content)
        logger.info(f"[Avatar] uploaded: {filename} ({len(content)} bytes)")
        return {"avatar_url": f"{settings.AVATAR_PUBLIC_URL}{filename}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Avatar] upload error: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


async def _download_and_save_avatar(temp_url: str, user_id: int) -> str:
    """从微信临时 URL 下载头像，保存到本地静态目录，返回可访问的 URL"""
    settings: Settings = get_settings()

    # 生成文件名：用户ID + 原URL哈希 + .jpg（避免重复下载）
    url_hash = hashlib.md5(temp_url.encode()).hexdigest()[:12]
    ext = ".jpeg"
    filename = f"u{user_id}_{url_hash}{ext}"
    save_path: Path = settings.AVATAR_SAVE_PATH / filename

    # 文件已存在则直接返回 URL（幂等）
    if save_path.exists():
        logger.info(f"[Avatar] file exists: {filename}")
        return f"{settings.AVATAR_PUBLIC_URL}{filename}"

    # 下载临时图片
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(temp_url)
            resp.raise_for_status()
            # 检查是否为图片内容类型
            ct = resp.headers.get("content-type", "")
            if "image" not in ct and len(resp.content) < 1000:
                raise ValueError(f"Not an image response, content-type={ct}")
            save_path.write_bytes(resp.content)
        logger.info(f"[Avatar] saved: {filename} ({len(resp.content)} bytes)")
        return f"{settings.AVATAR_PUBLIC_URL}{filename}"
    except Exception as e:
        logger.warning(f"[Avatar] download failed for user {user_id}: {e}")
        return ""  # 返回空字符串表示保存失败


@router.post("/login", response_model=LoginOut)
async def wechat_login(
    data: WechatLoginIn,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """微信登录 — code 换 openid，返回 JWT token"""
    client = WeChatClient(app_id=settings.WECHAT_APP_ID, app_secret=settings.WECHAT_APP_SECRET)
    try:
        openid = await client.get_openid(data.code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"WeChat login failed: {e}")
    finally:
        await client.close()

    # 查找或创建用户
    stmt = select(User).where(User.openid == openid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    is_new_user = False
    if not user:
        # 创建用户并生成默认昵称
        user = User(openid=openid)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        # 默认昵称：球迷{后4位id}
        user.nickname = f"球迷{user.id % 10000:04d}"
        await db.flush()
        is_new_user = True

    # 生成 JWT token
    token = create_token(user.id, settings.SECRET_KEY, settings.TOKEN_EXPIRE_HOURS)

    # 判断是否已完善资料：头像和昵称都不为空
    profile_setup = bool(user.avatar_url) and bool(user.nickname)

    return LoginOut(token=token, user=UserOut.model_validate(user), profile_setup=profile_setup, is_new_user=is_new_user)


@router.get("/vote", response_model=Optional[VoteOut])
async def get_user_vote(
    match_id: int = Query(..., description="比赛ID"),
    user_id: int = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
):
    """查询用户对某场比赛的投票"""
    cache_key = f"vote:{user_id}:{match_id}"

    async def fetch():
        stmt = select(UserVote).where(
            UserVote.user_id == user_id,
            UserVote.match_id == match_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    return await get_or_set(user_vote_cache, cache_key, fetch)


@router.post("/vote", response_model=VoteOut)
async def create_vote(
    data: VoteIn,
    user_id: int = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
):
    """用户投票预测"""
    # 验证用户存在
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # 验证比赛存在
    match_stmt = select(Match).where(Match.id == data.match_id)
    match_result = await db.execute(match_stmt)
    if not match_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Match not found")

    # 检查是否已投票 → 已投票则更新，未投票则新建
    stmt = select(UserVote).where(
        UserVote.user_id == user_id,
        UserVote.match_id == data.match_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        # 更新预测（比赛未结束时允许修改）
        existing.result = data.result
        existing.score_home = data.score_home
        existing.score_away = data.score_away
        existing.is_correct_result = None
        existing.is_correct_score = None
        await db.flush()
        await db.refresh(existing)
        # 写后失效缓存
        invalidate_user(user_id)
        return existing

    vote = UserVote(
        user_id=user_id,
        match_id=data.match_id,
        result=data.result,
        score_home=data.score_home,
        score_away=data.score_away,
    )
    db.add(vote)
    await db.flush()
    await db.refresh(vote)

    # 写后失效缓存
    invalidate_user(user_id)
    return vote


@router.get("/profile", response_model=UserProfileOut)
async def get_profile(
    user_id: int = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
):
    """用户信息"""
    cache_key = f"profile:{user_id}"

    async def fetch():
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 投票统计
        total_stmt = select(func.count(UserVote.id)).where(UserVote.user_id == user_id)
        total_result = await db.execute(total_stmt)
        total = total_result.scalar() or 0

        evaluated_stmt = (
            select(
                func.sum(case((UserVote.is_correct_result == True, 1), else_=0)).label("correct_result"),
                func.sum(case((UserVote.is_correct_score == True, 1), else_=0)).label("correct_score"),
            )
            .where(UserVote.user_id == user_id)
            .where(UserVote.is_correct_result.isnot(None))
        )
        evaluated_result = await db.execute(evaluated_stmt)
        evaluated_row = evaluated_result.one()
        correct_result = evaluated_row.correct_result or 0
        correct_score = evaluated_row.correct_score or 0

        vote_stats = {
            "total": total,
            "correct_result": correct_result,
            "correct_score": correct_score,
            "result_accuracy": round(correct_result / total * 100, 1) if total > 0 else 0,
        }

        user_dict = UserOut.model_validate(user).model_dump()
        user_dict["total_votes"] = total
        user_dict["correct_results"] = correct_result
        user_dict["correct_scores"] = correct_score

        return {"user": user_dict, "vote_stats": vote_stats}

    try:
        return await get_or_set(user_profile_cache, cache_key, fetch)
    except HTTPException:
        raise


@router.get("/votes", response_model=list[VoteHistoryItem])
async def get_vote_history(
    user_id: int = Query(..., description="用户ID"),
    limit: int = Query(20, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """获取用户投票历史"""
    cache_key = f"votes:{user_id}:{limit}:{offset}"

    async def fetch():
        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)
        stmt = (
            select(UserVote, Match, HomeTeam, AwayTeam)
            .join(Match, UserVote.match_id == Match.id)
            .join(HomeTeam, Match.home_team_id == HomeTeam.id)
            .join(AwayTeam, Match.away_team_id == AwayTeam.id)
            .where(UserVote.user_id == user_id)
            .order_by(UserVote.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        rows = result.all()

        items = []
        for row in rows:
            vote, match, home_team, away_team = row
            items.append(VoteHistoryItem(
                id=vote.id,
                match_id=match.id,
                round=match.round,
                match_time=match.match_time.isoformat() if match.match_time else None,
                home_team_name=home_team.cn_name or home_team.name,
                away_team_name=away_team.cn_name or away_team.name,
                home_team_flag=home_team.flag_url,
                away_team_flag=away_team.flag_url,
                match_status=match.status.value,
                match_result=match.result.value if match.result else None,
                match_home_score=match.home_score,
                match_away_score=match.away_score,
                predicted_result=vote.result.value,
                predicted_home_score=vote.score_home,
                predicted_away_score=vote.score_away,
                is_correct_result=vote.is_correct_result,
                is_correct_score=vote.is_correct_score,
                created_at=vote.created_at.isoformat() if vote.created_at else None,
            ))
        return items

    return await get_or_set(user_votes_cache, cache_key, fetch)


@router.put("/profile", response_model=UserOut)
async def update_profile(
    data: UpdateProfileIn,
    user_id: int = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
):
    """更新用户昵称/头像（微信临时 URL 会自动下载转存）"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.nickname is not None:
        user.nickname = data.nickname
    if data.avatar_url:
        # 检测是否为临时 URL（http://tmp/ 或 /tmp/），需要下载转存
        raw_url = data.avatar_url.strip()
        if "/tmp/" in raw_url.lower() or not raw_url.startswith("http"):
            saved_url = await _download_and_save_avatar(raw_url, user_id)
            user.avatar_url = saved_url or raw_url  # 下载失败时仍存原值（兜底）
        else:
            # 已是有效永久 URL，直接存
            user.avatar_url = raw_url

    await db.flush()
    await db.refresh(user)

    # 写后失效缓存
    invalidate_user(user_id)
    return UserOut.model_validate(user)
