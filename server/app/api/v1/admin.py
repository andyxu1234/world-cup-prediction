"""管理后台路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.services.match_sync import sync_matches
from app.services.ai_predictor import generate_predictions, generate_single_match_predictions
from app.services.prediction_evaluator import evaluate_predictions
from app.services.stats_sync import sync_standings_and_stats
from app.services.h2h_sync import sync_all_h2h
from app.services.sync_pipeline import sync_matches_and_respond
from app.services.vip_service import (
    get_vip_status,
    add_vip,
    renew_vip,
    delete_vip,
    get_vip_list,
    get_vip_stats,
)
from app.core.cache import clear_all_caches

router = APIRouter(prefix="/admin", tags=["admin"])


# VIP 相关的请求模型
class AddVipRequest(BaseModel):
    openid: str
    plan_type: str
    remark: Optional[str] = None


class RenewVipRequest(BaseModel):
    user_id: int
    plan_type: str


@router.post("/cache/clear")
async def trigger_clear_cache():
    """手动清空所有缓存（用于代码更新后立即生效）"""
    clear_all_caches()
    return {"message": "All caches cleared"}


@router.post("/pipeline/sync")
async def trigger_sync_pipeline():
    """手动触发完整同步流水线（同步比赛 + 事件驱动下游）"""
    try:
        result = await sync_matches_and_respond()
        return {"status": "ok", "message": "Sync pipeline completed", "detail": result}
    except Exception as e:
        logger.error(f"Sync pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync pipeline failed: {e}")


@router.post("/matches/sync")
async def trigger_sync_matches():
    """手动触发比赛数据同步"""
    try:
        result = await sync_matches()
        return {"status": "ok", "message": "Match sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Match sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Match sync failed: {e}")


@router.post("/stats/sync")
async def trigger_sync_stats():
    """手动触发统计同步（积分榜、球队统计、近期状态）"""
    try:
        result = await sync_standings_and_stats()
        return {"status": "ok", "message": "Stats sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Stats sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats sync failed: {e}")


@router.post("/h2h/sync")
async def trigger_sync_h2h():
    """手动触发H2H数据同步"""
    try:
        result = await sync_all_h2h()
        return {"status": "ok", "message": "H2H sync completed", "detail": result}
    except Exception as e:
        logger.error(f"H2H sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"H2H sync failed: {e}")


@router.post("/predictions/generate")
async def trigger_generate_predictions():
    """手动触发全部 AI 预测生成"""
    try:
        result = await generate_predictions()
        return {"status": "ok", "message": "Prediction generation completed", "detail": result}
    except Exception as e:
        logger.error(f"Prediction generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction generation failed: {e}")


@router.post("/predictions/generate/{match_id}")
async def trigger_generate_single_match(match_id: int):
    """手动触发单场比赛的 AI 预测"""
    try:
        result = await generate_single_match_predictions(match_id)
        return {"status": "ok", "message": f"Prediction generation completed for match {match_id}", "detail": result}
    except Exception as e:
        logger.error(f"Prediction generation for match {match_id} failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction generation failed: {e}")


@router.post("/predictions/evaluate")
async def trigger_evaluate_predictions():
    """手动触发预测评估"""
    try:
        result = await evaluate_predictions()
        return {"status": "ok", "message": "Prediction evaluation completed", "detail": result}
    except Exception as e:
        logger.error(f"Prediction evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction evaluation failed: {e}")


@router.post("/predictions/reevaluate")
async def trigger_reevaluate_predictions():
    """重新评估所有预测（修复比分命中率计算，考虑备选比分）"""
    try:
        result = await evaluate_predictions(force_recalculate=True)
        return {"status": "ok", "message": "Predictions re-evaluated with alt score logic", "detail": result}
    except Exception as e:
        logger.error(f"Prediction re-evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction re-evaluation failed: {e}")


# ==================== VIP 管理接口 ====================

@router.post("/vip/add")
async def add_vip_member(
    request: AddVipRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加 VIP 会员"""
    try:
        result = await add_vip(
            db=db,
            openid=request.openid,
            plan_type=request.plan_type,
            remark=request.remark,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"添加 VIP 会员失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加失败: {e}")


@router.get("/vip/list")
async def get_vip_members(
    db: AsyncSession = Depends(get_db),
):
    """获取 VIP 会员列表"""
    try:
        members = await get_vip_list(db=db)
        return members
    except Exception as e:
        logger.error(f"获取 VIP 列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {e}")


@router.post("/vip/renew")
async def renew_vip_member(
    request: RenewVipRequest,
    db: AsyncSession = Depends(get_db),
):
    """续费 VIP 会员"""
    try:
        result = await renew_vip(
            db=db,
            user_id=request.user_id,
            plan_type=request.plan_type,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"续费 VIP 会员失败: {e}")
        raise HTTPException(status_code=500, detail=f"续费失败: {e}")


@router.delete("/vip/{member_id}")
async def delete_vip_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除 VIP 会员"""
    try:
        result = await delete_vip(db=db, member_id=member_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"删除 VIP 会员失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.get("/vip/stats")
async def get_vip_statistics(
    db: AsyncSession = Depends(get_db),
):
    """获取 VIP 统计信息"""
    try:
        stats = await get_vip_stats(db=db)
        return stats
    except Exception as e:
        logger.error(f"获取 VIP 统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {e}")
