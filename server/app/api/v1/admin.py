"""管理后台路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.match_sync import sync_matches
from app.services.ai_predictor import generate_predictions, generate_single_match_predictions
from app.services.prediction_evaluator import evaluate_predictions
from app.services.stats_sync import sync_standings_and_stats
from app.services.h2h_sync import sync_all_h2h
from app.services.sync_pipeline import sync_matches_and_respond
from app.services.seed import seed_all, seed_ai_models, seed_teams, seed_matches, seed_predictions

router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.post("/seed")
async def trigger_seed_data():
    """初始化种子数据（AI模型、球队、比赛、预测）— 与现有数据合并"""
    try:
        await seed_all()
        return {"status": "ok", "message": "Seed data initialized successfully"}
    except Exception as e:
        logger.error(f"Seed data failed: {e}")
        raise HTTPException(status_code=500, detail=f"Seed data failed: {e}")
