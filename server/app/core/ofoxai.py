from __future__ import annotations

import json
from loguru import logger
from openai import AsyncOpenAI


class OfoxAIClient:
    """OfoxAI 统一 AI 网关客户端 — 通过 OpenAI 兼容接口调用所有 LLM 模型"""

    def __init__(self, api_key: str, base_url: str = "https://api.ofox.io/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """调用 OfoxAI Chat Completions API（OpenAI 兼容格式）"""
        import time
        _t_start = time.monotonic()
        logger.info(f"[OfoxAI] >>> REQUEST START | model={model} | base_url={self.client.base_url} | "
                     f"messages_count={len(messages)} | temperature={temperature} | max_tokens={max_tokens}")

        try:
            resp = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            _t_elapsed = time.monotonic() - _t_start
            content = resp.choices[0].message.content
            usage = getattr(resp, 'usage', None)
            finish_reason = resp.choices[0].finish_reason if resp.choices else 'unknown'
            logger.info(
                f"[OfoxAI] <<< REQUEST OK  | model={model} | "
                f"elapsed={_t_elapsed:.2f}s | "
                f"content_len={len(content)} | "
                f"finish_reason={finish_reason} | "
                f"usage={usage}"
            )
            return content
        except Exception as e:
            _t_elapsed = time.monotonic() - _t_start
            _exc_type = type(e).__name__
            _exc_msg = str(e)
            # 截断过长的错误信息
            if len(_exc_msg) > 500:
                _exc_msg = _exc_msg[:500] + '...(truncated)'
            logger.error(
                f"[OfoxAI] <<< REQUEST FAIL| model={model} | "
                f"elapsed={_t_elapsed:.2f}s | "
                f"exception={_exc_type} | "
                f"error={_exc_msg}"
            )
            raise

    async def predict_match(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        """单场预测便捷方法：构建 messages 并解析 JSON 响应"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        # 预测响应通常包含结构化JSON，需要较大输出窗口（部分模型如Gemini容易截断）
        content = await self.chat_completion(
            model=model, messages=messages, max_tokens=2048,
        )
        # 尝试解析 JSON（AI 可能返回 markdown 代码块包裹的 JSON）
        parsed = self._extract_json(content)
        if parsed is None:
            logger.error(f"[{model}] Failed to parse JSON from response (len={len(content)}), "
                        f"raw content preview: {content[:300]!r}")
            raise ValueError(f"Model [{model}] returned non-JSON content")
        return parsed

    @staticmethod
    def _extract_json(content: str) -> dict | None:
        """从 LLM 响应中提取 JSON，兼容多种格式"""
        import re
        if not content:
            return None

        # 策略1: 直接解析（纯 JSON）
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 策略2: markdown 代码块 ```json ... ``` 或 ``` ... ```
        code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        for block in matches:
            block = block.strip()
            if not block:
                continue
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

        # 策略3: 找到最外层 { } 包裹的完整 JSON 对象
        brace_start = content.find('{')
        if brace_start == -1:
            return None
        brace_end = content.rfind('}')
        if brace_end == -1 or brace_end <= brace_start:
            return None
        candidate = content[brace_start : brace_end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # 策略4: 尝试修复常见的截断/未终止字符串（补全未闭合的引号）
        repaired = re.sub(r'(?<!\\)"[^"]*$', '"', candidate)   # 未闭合字符串
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)      # 尾部多余逗号
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # 策略5: 处理严重截断——缺少闭合 } 的 JSON
        # 移除最后一个不完整的 key:value 对，补全闭合括号
        truncated = self._repair_truncated_json(candidate)
        if truncated is not None:
            try:
                return json.loads(truncated)
            except json.JSONDecodeError:
                pass

        # 策略5备用: 对原始 content 同样尝试截断修复（strategy3 可能因无 } 而跳过）
        if '{' in content and '}' not in content:
            raw_truncated = self._repair_truncated_json(content[content.find('{'):])
            if raw_truncated is not None:
                try:
                    return json.loads(raw_truncated)
                except json.JSONDecodeError:
                    pass

        return None

    @staticmethod
    def _repair_truncated_json(text: str) -> str | None:
        """修复严重截断的 JSON：移除末尾不完整的键值对，补全闭合符号"""
        import re
        # 找到最后一个完整的 value 后面跟着的逗号位置
        # 从后往前找模式: ,"key" 或最后一个已完成的值
        text = text.rstrip()

        # 如果已经以 } 或 ] 结尾，说明结构完整但可能有其他问题，直接返回
        if text.endswith('}') or text.endswith(']'):
            return text

        # 计算花括号和方括号的深度
        depth_brace = 0
        depth_bracket = 0
        last_complete_pos = -1  # 最后一个完整节点（逗号或起始{）的位置

        for i, ch in enumerate(text):
            if ch == '{':
                depth_brace += 1
            elif ch == '}':
                depth_brace -= 1
            elif ch == '[':
                depth_bracket += 1
            elif ch == ']':
                depth_bracket -= 1
            # 记录在顶层且紧跟完整值的逗号位置（即下一个 key 的起点之前）
            if ch == ',' and depth_brace == 1 and depth_bracket == 0:
                last_complete_pos = i

        if last_complete_pos > 0:
            # 截断到最后一个逗号之前，然后补全闭合
            trimmed = text[:last_complete_pos]  # 去掉尾部逗号及之后的不完整内容
        else:
            # 连一个完整 key:value 都没有，只能尽力补全
            trimmed = text

        # 补齐缺失的闭合符号
        closed = trimmed
        # 先闭合所有未闭合的方括号
        closed += ']' * max(0, depth_bracket)
        # 再闭合所有未闭合的花括号
        closed += '}' * max(0, depth_brace)
        # 清理尾部可能的逗号（截断点可能在逗号处）
        closed = re.sub(r',\s*([}\]]*)$', r'\1', closed)

        return closed

    async def close(self):
        await self.client.close()
