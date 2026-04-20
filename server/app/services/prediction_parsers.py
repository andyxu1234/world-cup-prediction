"""预测输出解析器 — 可插拔的 LLM 输出解析、校验与后处理

设计原则:
- 每个 Parser 类负责一种模型或一组模型的输出处理
- parse(): 原始 JSON → 标准化 dict
- validate(): 校验 + 后处理，失败抛出 ParseValidationError
- 通过 get_parser() 工厂函数按模型名获取对应 Parser
"""

from __future__ import annotations

from loguru import logger
from typing import Optional


class ParseValidationError(Exception):
    """输出校验失败，可触发重试"""
    pass


class BasePredictionParser:
    """预测输出解析器基类"""

    # 合法的 result 值
    VALID_RESULTS = {"home_win", "draw", "away_win"}

    def parse(self, raw: dict, model_name: str = "") -> dict:
        """解析原始 LLM JSON 输出为标准化格式

        子类可 override 此方法做模型特定的字段映射/清洗
        """
        return raw

    def validate(self, parsed: dict, model_name: str = "") -> dict:
        """校验并后处理解析后的预测结果

        Returns:
            校验后的 dict (可能被修正)

        Raises:
            ParseValidationError: 严重校验失败，应重试
        """
        result = parsed.get("result", "")
        if result not in self.VALID_RESULTS:
            # 尝试中文映射
            cn_map = {"主胜": "home_win", "平局": "draw", "客胜": "away_win"}
            if result in cn_map:
                parsed["result"] = cn_map[result]
                logger.debug(f"[{model_name}] Mapped result '{result}' → '{cn_map[result]}'")
            else:
                raise ParseValidationError(f"Invalid result: {result!r}, expected one of {self.VALID_RESULTS}")

        # 信心度归一化到 1-10
        confidence = parsed.get("confidence", 5)
        if not isinstance(confidence, (int, float)):
            confidence = 5
        parsed["confidence"] = max(1, min(10, int(confidence)))

        # 比分合理性校验
        score = parsed.get("score", {})
        home_score = score.get("home", 0)
        away_score = score.get("away", 0)
        if not isinstance(home_score, int) or not isinstance(away_score, int):
            score["home"] = int(home_score) if isinstance(home_score, (int, float)) else 0
            score["away"] = int(away_score) if isinstance(away_score, (int, float)) else 0
            parsed["score"] = score
        if home_score > 15 or away_score > 15:
            raise ParseValidationError(
                f"Abnormal score {home_score}:{away_score}, likely parsing error"
            )

        # score_alt 同样校验
        score_alt = parsed.get("score_alt")
        if score_alt and isinstance(score_alt, dict):
            for key in ("home", "away"):
                v = score_alt.get(key, 0)
                if not isinstance(v, (int, float)):
                    score_alt[key] = 0
            prob = score_alt.get("probability")
            if prob is not None:
                score_alt["probability"] = max(0.0, min(1.0, float(prob)))
            parsed["score_alt"] = score_alt

        # 确保 analysis 不为空
        if not parsed.get("analysis"):
            parsed["analysis"] = "模型未提供分析"

        return parsed


class GeminiParser(BasePredictionParser):
    """Gemini 模型专用解析器 — 处理截断和特殊格式"""

    def parse(self, raw: dict, model_name: str = "") -> dict:
        # Gemini 经常省略 score_alt，补上默认值
        if "score_alt" not in raw or raw["score_alt"] is None:
            raw["score_alt"] = {
                "home": raw.get("score", {}).get("home", 0),
                "away": raw.get("score", {}).get("away", 0),
                "probability": 0.3,
            }
            logger.debug(f"[{model_name}] Gemini: added default score_alt")

        # Gemini 有时 analysis 写成 reasoning
        if "reasoning" in raw and "analysis" not in raw:
            raw["analysis"] = raw.pop("reasoning")

        return raw


class DeepSeekParser(BasePredictionParser):
    """DeepSeek 模型解析器 — 格式通常标准，做基本处理"""

    def parse(self, raw: dict, model_name: str = "") -> dict:
        # DeepSeek 有时把 confidence 写成 confidence_level
        if "confidence_level" in raw and "confidence" not in raw:
            raw["confidence"] = raw.pop("confidence_level")
        return raw


class QwenParser(BasePredictionParser):
    """通义千问解析器 — 处理中文 result 和特殊格式"""

    def parse(self, raw: dict, model_name: str = "") -> dict:
        # 千问有时用中文 key
        if "结果" in raw and "result" not in raw:
            raw["result"] = raw.pop("结果")
        if "信心" in raw and "confidence" not in raw:
            raw["confidence"] = raw.pop("信心")
        if "分析" in raw and "analysis" not in raw:
            raw["analysis"] = raw.pop("分析")
        return raw


# ── Parser 注册表 ──────────────────────────────────────────────

# 模型名 → Parser 类的映射 (按模型名关键词匹配)
_PARSER_RULES: list[tuple[str, type[BasePredictionParser]]] = [
    ("gemini", GeminiParser),
    ("deepseek", DeepSeekParser),
    ("qwen", QwenParser),
    ("通义", QwenParser),
    ("bailian", QwenParser),
]

# 默认解析器
_DEFAULT_PARSER = BasePredictionParser()


def get_parser(model_name: str) -> BasePredictionParser:
    """根据模型名称获取对应的输出解析器"""
    name_lower = model_name.lower()
    for keyword, parser_cls in _PARSER_RULES:
        if keyword in name_lower:
            return parser_cls()
    return _DEFAULT_PARSER


def register_parser(keyword: str, parser_cls: type[BasePredictionParser]) -> None:
    """注册自定义解析器 (用于扩展)

    Usage:
        register_parser("my_model", MyModelParser)
    """
    _PARSER_RULES.insert(0, (keyword.lower(), parser_cls))
    logger.info(f"Registered parser {parser_cls.__name__} for keyword '{keyword}'")


# ── 汇总输出解析器 ──────────────────────────────────────────────

class SummaryParser:
    """汇总预测输出解析器 — 处理 DeepSeek 汇总的特殊格式"""

    def parse(self, raw: dict) -> dict:
        # 确保必要字段存在
        if "short_summary" not in raw or not raw["short_summary"]:
            raw["short_summary"] = "预测待定"
        if "summary" not in raw or not raw["summary"]:
            raw["summary"] = "综合分析生成失败"
        return raw

    def validate(self, parsed: dict) -> dict:
        result = parsed.get("result", "")
        valid = {"home_win", "draw", "away_win"}
        if result not in valid:
            cn_map = {"主胜": "home_win", "平局": "draw", "客胜": "away_win"}
            if result in cn_map:
                parsed["result"] = cn_map[result]
            else:
                logger.warning(f"Summary has invalid result: {result!r}")

        # 信心度校验
        confidence = parsed.get("confidence", 5)
        parsed["confidence"] = max(1, min(10, int(confidence))) if isinstance(confidence, (int, float)) else 5

        # 比分校验
        score = parsed.get("score", {})
        for key in ("home", "away"):
            v = score.get(key, 0)
            if not isinstance(v, (int, float)):
                score[key] = 0
        parsed["score"] = score

        return parsed
