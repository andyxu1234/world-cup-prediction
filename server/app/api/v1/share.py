"""分享相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.share import ShareCardOut
from app.services.share_card import get_share_card_data, generate_share_card_image

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
