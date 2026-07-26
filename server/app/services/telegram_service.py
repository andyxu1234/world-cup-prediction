"""Telegram 推送服务

支持向个人聊天和群组推送消息。
使用 Telegram Bot API 发送消息，支持 Markdown 格式。
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import get_settings


class TelegramService:
    """Telegram 消息推送服务"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = f"https://api.telegram.org/bot{self.settings.TELEGRAM_BOT_TOKEN}"

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
    ) -> bool:
        """发送消息到指定 Chat

        Args:
            chat_id: 目标 Chat ID（个人或群组）
            text: 消息内容（支持 Markdown 格式）
            parse_mode: 解析模式（Markdown/HTML）
            disable_web_page_preview: 禁用链接预览

        Returns:
            bool: 发送是否成功
        """
        if not self.settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token 未配置，跳过发送")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30)
                result = response.json()

                if result.get("ok"):
                    logger.info(f"Telegram 消息发送成功 -> {chat_id}")
                    return True
                else:
                    error_code = result.get("error_code")
                    description = result.get("description")
                    logger.error(
                        f"Telegram 消息发送失败: {error_code} - {description} -> {chat_id}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.error(f"Telegram 消息发送超时 -> {chat_id}")
            return False
        except Exception as e:
            logger.error(f"Telegram 消息发送异常: {e} -> {chat_id}")
            return False

    async def broadcast(self, text: str, parse_mode: str = "Markdown") -> dict:
        """广播消息到所有配置的 Chat

        Args:
            text: 消息内容
            parse_mode: 解析模式

        Returns:
            dict: {"success": int, "failed": int, "total": int}
        """
        if not self.settings.TELEGRAM_CHAT_IDS:
            logger.warning("Telegram Chat IDs 未配置，跳过广播")
            return {"success": 0, "failed": 0, "total": 0}

        chat_ids = [
            cid.strip()
            for cid in self.settings.TELEGRAM_CHAT_IDS.split(",")
            if cid.strip()
        ]

        success_count = 0
        failed_count = 0

        for chat_id in chat_ids:
            result = await self.send_message(chat_id, text, parse_mode)
            if result:
                success_count += 1
            else:
                failed_count += 1

        logger.info(
            f"Telegram 广播完成: {success_count} 成功, {failed_count} 失败, "
            f"共 {len(chat_ids)} 个目标"
        )

        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(chat_ids),
        }

    async def get_me(self) -> dict | None:
        """获取 Bot 信息（用于验证 Token 是否有效）

        Returns:
            dict: Bot 信息，失败返回 None
        """
        if not self.settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token 未配置")
            return None

        url = f"{self.base_url}/getMe"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                result = response.json()

                if result.get("ok"):
                    bot_info = result.get("result", {})
                    logger.info(
                        f"Telegram Bot 验证成功: @{bot_info.get('username')} "
                        f"(ID: {bot_info.get('id')})"
                    )
                    return bot_info
                else:
                    logger.error(f"Telegram Bot 验证失败: {result}")
                    return None

        except Exception as e:
            logger.error(f"Telegram Bot 验证异常: {e}")
            return None


# 全局单例
_telegram_service: TelegramService | None = None


def get_telegram_service() -> TelegramService:
    """获取 Telegram 服务单例"""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service
