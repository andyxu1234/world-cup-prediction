#!/usr/bin/env python3
"""测试 Telegram 推送服务

使用方法：
1. 确保已在 .env 中配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_IDS
2. 运行此脚本：python scripts/test_telegram.py

依赖：pip install httpx python-dotenv
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def test_telegram():
    """测试 Telegram 服务"""

    print("=" * 50)
    print("🧪 Telegram 推送服务测试")
    print("=" * 50)
    print()

    # 测试 1: 配置检查
    print("1️⃣ 检查配置...")
    from app.config import get_settings

    settings = get_settings()

    if not settings.TELEGRAM_BOT_TOKEN:
        print("   ❌ TELEGRAM_BOT_TOKEN 未配置")
        return
    else:
        print(f"   ✅ Bot Token: {settings.TELEGRAM_BOT_TOKEN[:10]}...")

    if not settings.TELEGRAM_CHAT_IDS:
        print("   ❌ TELEGRAM_CHAT_IDS 未配置")
        return
    else:
        chat_ids = [cid.strip() for cid in settings.TELEGRAM_CHAT_IDS.split(",") if cid.strip()]
        print(f"   ✅ Chat IDs: {len(chat_ids)} 个目标")
        for cid in chat_ids:
            print(f"      - {cid}")

    print()

    # 测试 2: Bot 连接
    print("2️⃣ 测试 Bot 连接...")
    from app.services.telegram_service import get_telegram_service

    telegram = get_telegram_service()
    bot_info = await telegram.get_me()

    if bot_info:
        print(f"   ✅ Bot 连接成功")
        print(f"      用户名: @{bot_info.get('username')}")
        print(f"      名称: {bot_info.get('first_name')}")
        print(f"      ID: {bot_info.get('id')}")
    else:
        print("   ❌ Bot 连接失败")
        return

    print()

    # 测试 3: 发送测试消息
    print("3️⃣ 发送测试消息...")

    test_message = (
        "🧪 *Telegram 推送测试*\n"
        "\n"
        "这是一条测试消息，用于验证推送功能是否正常。\n"
        "\n"
        "✅ 如果你看到这条消息，说明配置成功！\n"
        "\n"
        "_来自 World Cup AI Prediction_"
    )

    result = await telegram.broadcast(test_message)

    if result["success"] > 0:
        print(f"   ✅ 消息发送成功")
        print(f"      成功: {result['success']} 个")
        print(f"      失败: {result['failed']} 个")
        print(f"      总计: {result['total']} 个")
    else:
        print("   ❌ 消息发送失败")
        return

    print()

    # 测试 4: 格式化函数
    print("4️⃣ 测试消息格式化...")

    from app.services.telegram_formatter import (
        format_daily_summary,
        format_finished_matches_summary,
        format_leaderboard_update,
    )

    # 模拟比赛数据
    test_matches = [
        {
            "id": 1,
            "match_time": "2026-07-24T20:00:00+08:00",
            "status": "not_started",
            "league_name": "English Premier League",
            "home_team": "曼联",
            "away_team": "利物浦",
        },
        {
            "id": 2,
            "match_time": "2026-07-24T22:00:00+08:00",
            "status": "not_started",
            "league_name": "English Premier League",
            "home_team": "阿森纳",
            "away_team": "切尔西",
        },
    ]

    # 使用正确的字段名称：home_win/draw/away_win
    test_predictions = {
        1: [
            {"model_name": "DeepSeek", "predicted_result": "home_win", "predicted_home_score": 2, "predicted_away_score": 1, "confidence": 75},
            {"model_name": "GPT", "predicted_result": "home_win", "predicted_home_score": 2, "predicted_away_score": 0, "confidence": 80},
            {"model_name": "Claude", "predicted_result": "draw", "predicted_home_score": 1, "predicted_away_score": 1, "confidence": 65},
        ],
        2: [
            {"model_name": "DeepSeek", "predicted_result": "draw", "predicted_home_score": 1, "predicted_away_score": 1, "confidence": 70},
            {"model_name": "GPT", "predicted_result": "home_win", "predicted_home_score": 2, "predicted_away_score": 1, "confidence": 75},
        ],
    }

    # 测试每日摘要格式化
    daily_message = format_daily_summary(test_matches, test_predictions, "2026年07月24日")
    print("   ✅ 每日摘要格式化成功")
    print("   预览:")
    for line in daily_message.split("\n")[:10]:
        print(f"      {line}")
    if len(daily_message.split("\n")) > 10:
        print("      ...")

    print()

    # 测试昨日赛果格式化
    test_finished = [
        {
            "league_name": "English Premier League",
            "home_team": "曼城",
            "away_team": "热刺",
            "home_score": 3,
            "away_score": 1,
        },
    ]

    finished_message = format_finished_matches_summary(test_finished)
    print("   ✅ 昨日赛果格式化成功")
    print("   预览:")
    for line in finished_message.split("\n"):
        print(f"      {line}")

    print()

    # 测试排行榜格式化
    test_leaderboard = [
        {"model_name": "DeepSeek", "result_accuracy": 75.5, "score_accuracy": 35.2},
        {"model_name": "GPT", "result_accuracy": 72.3, "score_accuracy": 32.1},
        {"model_name": "Claude", "result_accuracy": 70.1, "score_accuracy": 30.5},
    ]

    leaderboard_message = format_leaderboard_update(test_leaderboard, top_n=3)
    print("   ✅ 排行榜格式化成功")
    print("   预览:")
    for line in leaderboard_message.split("\n"):
        print(f"      {line}")

    print()

    # 测试完成
    print("=" * 50)
    print("✅ 所有测试通过！")
    print("=" * 50)
    print()
    print("下一步：")
    print("1. 启动后端服务：uvicorn app.main:app --reload")
    print("2. 访问 API 文档：http://localhost:8000/docs")
    print("3. 测试管理接口：/admin/telegram/*")
    print("4. 等待每日 22:00 自动推送，或手动触发：POST /admin/telegram/push")


if __name__ == "__main__":
    asyncio.run(test_telegram())
