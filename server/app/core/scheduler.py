"""定时任务调度

重构后只有 2 个 cron job：
- sync_matches_and_respond: 每 30 分钟同步比赛 + 事件驱动下游（H2H、stats、评估）
- generate_predictions: 每日 01:00 生成 AI 预测
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

scheduler = AsyncIOScheduler()


def start_scheduler():
    """启动定时任务"""
    from app.services.sync_pipeline import sync_matches_and_respond
    from app.services.ai_predictor import generate_predictions

    # 每 30 分钟：同步比赛 + 事件响应（新增比赛→H2H，比赛结束→stats+评估）
    scheduler.add_job(
        sync_matches_and_respond,
        "cron",
        minute="*/30",
        id="sync_matches_and_respond",
        replace_existing=True,
    )

    # 每日 01:00：生成 AI 预测
    scheduler.add_job(
        generate_predictions,
        "cron",
        hour=1,
        minute=0,
        id="generate_predictions",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: "
        "sync_matches_and_respond(*/30min), "
        "generate_predictions(01:00)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
