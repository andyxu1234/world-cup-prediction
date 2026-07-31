"""Telegram 频道连通性零依赖探测脚本（仅用标准库，无需安装任何第三方包）

用途：在任意机器上快速验证
  1. TELEGRAM_BOT_TOKEN 是否有效（getMe）
  2. bot 是否已被加为频道 -1002237821804 的管理员（能否发消息）

用法（在 server/ 目录下）：
  python scripts/tg_connectivity_check.py

读取 server/.env 中的 TELEGRAM_BOT_TOKEN / TELEGRAM_PUBLIC_CHANNEL_ID。
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(os.path.dirname(_HERE), ".env")
_DEFAULT_CHANNEL = "-1002237821804"


def _load_env() -> dict:
    env: dict = {}
    if not os.path.exists(_ENV_PATH):
        return env
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def _api(token: str, method: str, payload: dict | None = None, proxy: str = "") -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if proxy:
        # 通过 HTTP/HTTPS 代理隧道（CONNECT）访问 Telegram
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy}))
        with opener.open(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _detect_proxy() -> str:
    """探测可用代理：TG_PROXY > HTTPS_PROXY > HTTP_PROXY > POLYMARKET_PROXY"""
    import os as _os

    for key in ("TG_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "POLYMARKET_PROXY"):
        val = _os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def main() -> None:
    env = _load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    channel = env.get("TELEGRAM_PUBLIC_CHANNEL_ID", "") or _DEFAULT_CHANNEL

    if not token:
        print("ERROR: 未在 .env 找到 TELEGRAM_BOT_TOKEN")
        return

    proxy = ""
    for key in ("TG_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "POLYMARKET_PROXY"):
        if env.get(key):
            proxy = env[key]
            break
    if not proxy:
        for key in ("TG_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "POLYMARKET_PROXY"):
            if os.environ.get(key):
                proxy = os.environ[key]
                break
    if proxy:
        print(f"使用代理: {proxy}")

    print(f"频道目标: {channel}")
    print("--- 1) 验证 Bot Token (getMe) ---")
    try:
        me = _api(token, "getMe", proxy=proxy)
    except urllib.error.URLError as e:
        print(f"网络错误（本机可能无法直连 api.telegram.org，需在能访问 TG 的机器/服务器上运行）: {e}")
        return
    except Exception as e:
        print(f"getMe 失败: {e}")
        return

    if not me.get("ok"):
        print(f"Token 无效: {me}")
        return
    bot = me["result"]
    print(f"  OK -> Bot @{bot.get('username')} (id={bot.get('id')})")

    print("--- 2) 发送测试消息到频道 ---")
    text = "🔧 连通性测试（可删除）"
    try:
        res = _api(token, "sendMessage", {"chat_id": channel, "text": text}, proxy=proxy)
    except urllib.error.URLError as e:
        print(f"网络错误: {e}")
        return
    except Exception as e:
        print(f"发送异常: {e}")
        return

    if res.get("ok"):
        msg = res.get("result", {})
        print(f"  OK -> 消息已发送到频道，message_id={msg.get('message_id')}")
        print("✅ 连通性测试通过：bot 已具备该频道发消息权限。")
    else:
        code = res.get("error_code")
        desc = res.get("description")
        print(f"  FAIL -> {code} {desc}")
        if code == 403:
            print("  说明：bot 不是该频道管理员。请到频道 → 管理频道 → 管理员 → 添加 bot 并授予发消息权限后重试。")
        print("❌ 连通性测试未通过。")


if __name__ == "__main__":
    main()
