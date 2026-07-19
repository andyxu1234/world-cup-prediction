"""定时任务调度

重构后只有 3 个 cron job：
- sync_matches_and_respond: 每 30 分钟同步比赛 + 事件驱动下游
- generate_predictions: 每日 01:00 生成 AI 预测
- refresh_all_caches: 每 5 分钟刷新缓存
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

scheduler = AsyncIOScheduler()


def start_scheduler():
    """启动定时任务"""
    from app.services.sync_pipeline import sync_matches_and_respond
    from app.services.ai_predictor import generate_predictions
    from app.services.stats_sync import sync_standings_and_stats
    from app.core.cache_warmer import refresh_all_caches

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

    # 每日 02:00：全量同步积分榜 + 球队统计 + 近期战绩
    scheduler.add_job(
        sync_standings_and_stats,
        "cron",
        hour=2,
        minute=0,
        id="sync_standings_and_stats",
        replace_existing=True,
    )

    # 每 5 分钟：刷新缓存（预热只读数据，减少 DB 查询）
    scheduler.add_job(
        refresh_all_caches,
        "cron",
        minute="*/5",
        id="refresh_all_caches",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: "
        "sync_matches_and_respond(*/30min), "
        "generate_predictions(01:00), "
        "sync_standings_and_stats(02:00), "
        "refresh_all_caches(*/5min)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
