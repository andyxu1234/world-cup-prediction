"""AI 预测生成服务 — 基于 LangGraph 编排"""

from __future__ import annotations

from loguru import logger

from app.services.prediction_graph import get_prediction_app


def _default_state(match_id=None) -> dict:
    """构建 LangGraph 初始状态 dict"""
    return {
        "match_id": match_id,
        "match_data_list": [],
        "models": [],
        "predictions": [],
        "failed": [],
        "skipped": 0,
        "summary_model_id": "deepseek/deepseek-v3.2",
        "summary_raw": None,
        "summary": None,
        "retry_count": 0,
        "max_retries": 2,
        "total_models": 0,
        "total_matches": 0,
        "completed_matches": 0,
    }


async def generate_predictions():
    """定时任务：为未来3天内未预测的比赛生成 AI 预测 (LangGraph 版)"""
    logger.info("Starting AI prediction generation (LangGraph)")

    app = get_prediction_app()

    try:
        result = await app.ainvoke(_default_state(match_id=None))

        logger.info(
            f"AI prediction generation completed: "
            f"{len(result.get('predictions', []))} predictions, "
            f"{len(result.get('failed', []))} failed, "
            f"{result.get('skipped', 0)} skipped, "
            f"{result.get('completed_matches', 0)} matches processed"
        )
        return {
            "predictions": len(result.get("predictions", [])),
            "failed": len(result.get("failed", [])),
            "skipped": result.get("skipped", 0),
            "matches": result.get("completed_matches", 0),
        }
    except Exception as e:
        logger.error(f"AI prediction generation failed: {e}")
        raise


async def generate_single_match_predictions(match_id: int):
    """手动触发单场比赛的 AI 预测（管理接口用）"""
    logger.info(f"Starting prediction for match {match_id} (LangGraph)")

    app = get_prediction_app()

    try:
        result = await app.ainvoke(_default_state(match_id=match_id))

        logger.info(
            f"Match {match_id} prediction completed: "
            f"{len(result.get('predictions', []))} predictions, "
            f"{len(result.get('failed', []))} failed"
        )
        return {
            "predictions": len(result.get("predictions", [])),
            "failed": len(result.get("failed", [])),
            "skipped": result.get("skipped", 0),
        }
    except Exception as e:
        logger.error(f"Prediction for match {match_id} failed: {e}")
        raise
