"""定时任务调度

共 8 个 cron job：
- sync_matches_and_respond: 每 30 分钟同步比赛 + 事件驱动下游
- generate_predictions: 每日 01:00 生成 AI 预测
- sync_standings_and_stats: 每日 02:00 同步积分榜 + 球队统计
- refresh_all_caches: 每 5 分钟刷新缓存
- sync_odds: 每 6 小时同步赛前赔率
- sync_polymarket: 每日 00:30 拉取 Polymarket 未来7天胜负平市场
- sync_standalone_markets: 每日 03:00 拉取 Polymarket 通用市场
- telegram_daily_push: 每日 22:00 Telegram 推送比赛和预测
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
    from app.services.odds_service import sync_all_upcoming_odds
    from app.services.polymarket_sync import sync_polymarket_events
    from app.services.polymarket_standalone_sync import sync_standalone_markets
    from app.core.cache_warmer import refresh_all_caches
    from app.services.telegram_daily_push import daily_push

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

    # 每 6 小时：同步赛前赔率（prematch），保证赔率及时更新
    # 注意：当前 match_odds.snapshot_date 为日期型，同日多次拉取会互相覆盖（仅留当天最后值），
    # 不会累积日内多快照。如需真·小时级走势，需为 match_odds 增加 snapshot_ts 并改唯一键。
    scheduler.add_job(
        sync_all_upcoming_odds,
        "cron",
        hour="*/6",
        minute=0,
        id="sync_odds",
        replace_existing=True,
    )

    # 每日 00:30：拉取 Polymarket 未来7天（五大联赛+欧冠+欧联）胜负平市场
    # 落 polymarket_events / polymarket_markets 两表；错开 00:00 的赔率同步，
    # 且早于 01:00 的 AI 预测（后续如需喂给预测可直接用当日数据）。
    scheduler.add_job(
        sync_polymarket_events,
        "cron",
        hour=0,
        minute=30,
        id="sync_polymarket",
        replace_existing=True,
    )

    # 每日 03:00：拉取 Polymarket 通用市场（用于 NO farming 等策略）
    # 独立于 polymarket_events 同步，拉取所有活跃市场并过滤
    scheduler.add_job(
        sync_standalone_markets,
        "cron",
        hour=3,
        minute=0,
        id="sync_standalone_markets",
        replace_existing=True,
    )

    # 每日 22:00：Telegram 推送今日比赛预测和昨日赛果
    # 推送内容包括：今日比赛列表、AI 预测汇总、昨日赛果、AI 排行榜（周一）
    scheduler.add_job(
        daily_push,
        "cron",
        hour=22,
        minute=0,
        id="telegram_daily_push",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: "
        "sync_matches_and_respond(*/30min), "
        "generate_predictions(01:00), "
        "sync_standings_and_stats(02:00), "
        "sync_odds(*/6h), "
        "sync_polymarket(00:30), "
        "sync_standalone_markets(03:00), "
        "refresh_all_caches(*/5min), "
        "telegram_daily_push(22:00)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
