"""分享相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.schemas.share import ShareCardOut
from app.services.share_card import get_share_card_data, generate_share_card_image, generate_invite_card_image


class InviteCardParams(BaseModel):
    nickname: str = "预言家"
    avatar_url: str = ""
    total_votes: int = 0
    correct_results: int = 0
    correct_scores: int = 0
    ai_ranking: list[dict] | None = None


router = APIRouter(prefix="/share", tags=["share"])


@router.get("/card/{match_id}", response_model=ShareCardOut)
async def get_share_card(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取分享卡片数据（JSON）"""
    try:
        data = await get_share_card_data(db, match_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/card/{match_id}/image")
async def get_share_card_image(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """生成分享卡片图片（PNG）"""
    try:
        data = await get_share_card_data(db, match_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        image_bytes = generate_share_card_image(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    return Response(content=image_bytes, media_type="image/png")


@router.get("/invite/card/image")
async def get_invite_card_image(
    nickname: str = Query(default="预言家", description="用户昵称"),
    avatar_url: str = Query(default="", description="头像 URL"),
    total_votes: int = Query(default=0, ge=0),
    correct_results: int = Query(default=0, ge=0),
    correct_scores: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """生成邀请卡图片（PNG）—— 用于个人中心分享好友"""
    # 获取 AI 排行榜 top 3
    ai_ranking = []
    try:
        from sqlalchemy import func
        from app.models.ai_model import AIModel

        stmt = (
            select(
                AIModel.name,
                AIModel.total,
                AIModel.correct_result,
            )
            .where(AIModel.total > 0)
            .order_by(
                (func.cast(AIModel.correct_result, float) / func.nullif(AIModel.total, 0)).desc()
            )
            .limit(3)
        )
        result = await db.execute(stmt)
        for row in result:
            total = row[1] or 0
            correct = row[2] or 0
            acc = (correct / total * 100) if total > 0 else 0.0
            ai_ranking.append({"name": row[0], "result_accuracy": acc})
    except Exception:
        # 默认数据兜底
        ai_ranking = [
            {"name": "DeepSeek", "result_accuracy": 82.3},
            {"name": "GPT-4o", "result_accuracy": 78.1},
            {"name": "Claude", "result_accuracy": 75.6},
        ]

    data = {
        "nickname": nickname or "预言家",
        "avatar_url": avatar_url,
        "total_votes": total_votes,
        "correct_results": correct_results,
        "correct_scores": correct_scores,
        "ai_ranking": ai_ranking,
    }

    try:
        image_bytes = generate_invite_card_image(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invite card generation failed: {e}")

    return Response(content=image_bytes, media_type="image/png")
