#!/usr/bin/env python3
"""获取 Telegram Chat ID 辅助脚本

使用方法：
1. 确保已在 .env 中配置 TELEGRAM_BOT_TOKEN
2. 运行此脚本：python scripts/get_telegram_chat_id.py
3. 向你的 Bot 发送任意消息
4. 脚本会显示你的 Chat ID

依赖：pip install httpx python-dotenv
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from dotenv import load_dotenv
import os

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def get_chat_ids():
    """获取与 Bot 交互的 Chat ID 列表"""

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        print("❌ 错误：未找到 TELEGRAM_BOT_TOKEN 配置")
        print(f"请在 {env_path} 中配置 TELEGRAM_BOT_TOKEN")
        return

    print(f"✅ Bot Token: {bot_token[:10]}...{bot_token[-5:]}")
    print()
    print("📱 请在 Telegram 中向你的 Bot 发送任意消息...")
    print("   （如果没有对话，先搜索你的 Bot 用户名并开始对话）")
    print()
    input("发送消息后，按 Enter 键继续...")
    print()

    # 获取更新
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            result = response.json()

            if not result.get("ok"):
                print(f"❌ API 请求失败: {result.get('description', '未知错误')}")
                return

            updates = result.get("result", [])

            if not updates:
                print("⚠️  未找到任何消息")
                print("   请确保：")
                print("   1. Bot Token 正确")
                print("   2. 已向 Bot 发送过消息")
                print("   3. Bot 未被禁用")
                return

            # 提取所有唯一的 Chat ID
            chat_ids = {}
            for update in updates:
                message = update.get("message", {})
                chat = message.get("chat", {})
                chat_id = chat.get("id")
                chat_type = chat.get("type", "")
                chat_title = chat.get("title", "")
                first_name = chat.get("first_name", "")
                username = chat.get("username", "")

                if chat_id and chat_id not in chat_ids:
                    chat_ids[chat_id] = {
                        "type": chat_type,
                        "title": chat_title,
                        "first_name": first_name,
                        "username": username,
                    }

            print(f"✅ 找到 {len(chat_ids)} 个 Chat ID：")
            print()
            print("-" * 50)

            for chat_id, info in chat_ids.items():
                if info["type"] == "private":
                    name = info["first_name"]
                    if info["username"]:
                        name += f" (@{info['username']})"
                    print(f"👤 个人聊天：{name}")
                elif info["type"] == "group":
                    name = info["title"] or "未知群组"
                    print(f"👥 群组：{name}")
                elif info["type"] == "supergroup":
                    name = info["title"] or "未知超级群组"
                    print(f"👥 超级群组：{name}")
                elif info["type"] == "channel":
                    name = info["title"] or "未知频道"
                    print(f"📢 频道：{name}")
                else:
                    print(f"❓ 其他类型 ({info['type']})")

                print(f"   Chat ID: {chat_id}")
                print()

            print("-" * 50)
            print()
            print("📝 将以下配置添加到 .env 文件：")
            print()

            # 生成配置示例
            chat_ids_str = ",".join(str(cid) for cid in chat_ids.keys())
            print(f"TELEGRAM_CHAT_IDS={chat_ids_str}")
            print()

    except httpx.TimeoutException:
        print("❌ 请求超时，请检查网络连接")
    except Exception as e:
        print(f"❌ 发生错误: {e}")


async def main():
    """主函数"""
    print("=" * 50)
    print("🤖 Telegram Chat ID 获取工具")
    print("=" * 50)
    print()

    await get_chat_ids()

    print()
    print("=" * 50)
    print("完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
