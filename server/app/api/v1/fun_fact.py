"""动态生成趣味文案 — 调用 DeepSeek"""

import json
from fastapi import APIRouter
from pydantic import BaseModel
from loguru import logger
from openai import AsyncOpenAI
from app.config import get_settings
from app.core.cache import fun_fact_cache, get_or_set

router = APIRouter(prefix="/fun-fact", tags=["fun-fact"])

SYSTEM_PROMPT = """你是一个足球世界杯小程序的"趣味小编"。你的任务是生成一条简短有趣的文案（关于世界杯、AI预测、足球冷知识等）。
要求：
1. 文案必须简洁，不超过50个字
2. 风格轻松幽默，带一点调侃或惊喜感
3. 内容围绕以下主题之一随机选择：世界杯历史冷知识、AI预测足球的有趣现象、足球比赛的意外数据、2026世界杯新看点
4. 每次都要不同，不要重复
5. 可以适当使用 emoji 增加趣味性
6. 用中文输出"""

USER_PROMPT = """请生成一条趣味文案。

请以 JSON 格式返回，包含字段：
{"icon": "一个emoji图标", "title": "标题（4-6字）", "text": "正文内容"}"""


class FunFactOut(BaseModel):
    icon: str
    title: str
    text: str


async def _call_deepseek() -> dict:
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY 未配置")

    client = AsyncOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com/v1",
    )

    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT},
            ],
            temperature=0.9,
            max_tokens=200,
        )
        content = resp.choices[0].message.content.strip()

        # 解析 JSON 响应
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 策略 2: markdown 代码块
        import re
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 策略 3: 找 JSON 对象
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[fun-fact] 无法解析 DeepSeek 返回的 JSON, raw: {content[:200]}")
        raise ValueError("AI 返回格式异常")

    finally:
        await client.close()


@router.get("", response_model=FunFactOut)
async def get_fun_fact():
    """调用 DeepSeek 动态生成趣味文案（全局缓存 1 小时，所有用户共享）"""
    cache_key = "latest"

    async def fetch():
        result = await _call_deepseek()
        return FunFactOut(
            icon=result.get("icon", "🎵"),
            title=result.get("title", "你知道吗？"),
            text=result.get("text", "精彩内容加载中..."),
        )

    try:
        return await get_or_set(fun_fact_cache, cache_key, fetch)
    except Exception as e:
        logger.error(f"[fun-fact] 生成失败: {e}")
        return FunFactOut(
            icon="⚽",
            title="足球小知识",
            text="世界杯历史上只有8个国家拿过冠军，你猜谁是第一？",
        )
