"""公共频道发帖脚本（手动 / 测试用）

前置：在 server/.env 配置 TELEGRAM_BOT_TOKEN，且 bot 已加入频道 -1002237821804 并设为管理员。

用法（在 server/ 目录下执行）：
  python scripts/post_to_channel.py --test       # 测试 bot 连接 + 频道发送权限（发一条可删除的探测消息）
  python scripts/post_to_channel.py --preview     # 仅预览将发送的内容，不实际发送
  python scripts/post_to_channel.py --push       # 实际发送到公共频道

说明：
  - 该脚本复用后端同一套 build_daily_messages，因此预览/发送内容与每日 22:00 自动推送完全一致。
  - 需要在能连上数据库的环境运行（脚本会查询比赛与预测数据）。
  - 频道 ID 来自配置 TELEGRAM_PUBLIC_CHANNEL_ID（默认 -1002237821804）。
"""

from __future__ import annotations

import asyncio
import os
import sys

# 让脚本能 import app 包（脚本位于 server/scripts/，需把 server/ 加入路径）
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from app.config import get_settings
from app.services.telegram_service import get_telegram_service
from app.services.telegram_daily_push import build_daily_messages, _channel_footer


async def _run(mode: str) -> None:
    settings = get_settings()
    tg = get_telegram_service()

    if mode == "--test":
        bot_info = await tg.get_me()
        print("Bot:", bot_info)
        print("Public channel id:", settings.TELEGRAM_PUBLIC_CHANNEL_ID)
        ok = await tg.send_to_public_channel("🔧 频道发帖联通测试（可删除）")
        print("Channel send ok:", ok)
        if not ok:
            print("提示：请确认 bot 已加入频道且为管理员（具备发消息权限）。")
        return

    messages = await build_daily_messages()
    footer = _channel_footer()

    if mode == "--preview":
        for title, text in messages:
            print("=" * 48)
            print(title)
            print("=" * 48)
            print(text + footer)
            print()
        print(f"共 {len(messages)} 条（预览模式，未实际发送）")
        return

    if mode == "--push":
        if not settings.TELEGRAM_BOT_TOKEN:
            print("ERROR: TELEGRAM_BOT_TOKEN 未配置")
            return
        if not settings.TELEGRAM_PUBLIC_CHANNEL_ID:
            print("ERROR: TELEGRAM_PUBLIC_CHANNEL_ID 未配置")
            return
        ok_count = 0
        for title, text in messages:
            ok = await tg.send_to_public_channel(text + footer)
            print(f"{title}: {'OK' if ok else 'FAIL'}")
            if ok:
                ok_count += 1
        print(f"发送完成 {ok_count}/{len(messages)}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--preview"
    if mode not in ("--test", "--preview", "--push"):
        print(__doc__)
        sys.exit(1)
    asyncio.run(_run(mode))


if __name__ == "__main__":
    main()
