# LangGraph 预测流程设计文档

## 概述

将 `generate_predictions` 中"多模型串行预测 + DeepSeek 汇总"的朴素 for 循环逻辑，重构为基于 **LangGraph StateGraph + Output Parser** 的可扩展架构。

核心改进：
- **并行化**：串行 for 循环 → `asyncio.gather` 并行，单场预测从 ~40-60s 降至 ~5-8s
- **可插拔输出处理**：不同 LLM 模型可通过独立 Parser 类自定义解析/校验逻辑
- **自动重试**：校验失败的预测通过条件边自动重试（最多 2 次）
- **可扩展**：新增处理步骤 = 新增节点 + 边，不修改已有代码

---

## 架构图

### 流程图

```
[load_match] → [parallel_predict] → [validate_outputs] ──→ [aggregate] → END
                                         ↑                      ↓ (校验失败)
                                    [retry_failed] ←──────────┘
```

### 节点说明

| 节点 | 职责 | 关键逻辑 |
|---|---|---|
| `load_match` | 加载比赛数据、活跃模型列表、已有预测 | 单场模式 / 批量模式（未来3天） |
| `parallel_predict` | 并行调用所有 LLM 模型 | `asyncio.gather`，已有预测跳过 |
| `validate_outputs` | 用 Output Parser 解析+校验每个预测 | 按 model_name 自动匹配 Parser |
| `retry_failed` | 对校验失败的预测重试 | 条件边 `_should_retry` 控制，最多 2 次 |
| `aggregate` | 用汇总模型综合所有预测，写入 DB | DeepSeek 汇总 + SummaryParser |

---

## State 定义

`PredictionState` 是 LangGraph 节点间流转的数据结构：

```python
class PredictionState(dict):
    # ── 输入 ──
    match_id: Optional[int] = None        # None = 批量模式
    match_data_list: list[dict] = []      # 序列化的比赛信息
    models: list[dict] = []               # 活跃模型列表
    existing_model_ids: list[int] = []    # 已有预测的模型 ID

    # ── 预测阶段 ──
    predictions: list[dict] = []          # 成功的预测
    failed: list[dict] = []               # 失败的预测
    skipped: int = 0                      # 跳过的已有预测数

    # ── 汇总阶段 ──
    summary_model_id: str = "deepseek/deepseek-v3.2"
    summary_raw: Optional[dict] = None
    summary: Optional[dict] = None

    # ── 控制流 ──
    retry_count: int = 0
    max_retries: int = 2
```

---

## Output Parser 设计

### 设计原则

- 每个 Parser 类负责一种模型或一组模型的输出处理
- `parse()`: 原始 JSON → 标准化 dict（字段映射、格式清洗）
- `validate()`: 校验 + 后处理，严重失败抛出 `ParseValidationError` 触发重试
- 通过 `get_parser(model_name)` 工厂函数按模型名自动匹配 Parser
- 通过 `register_parser(keyword, cls)` 运行时注册自定义 Parser

### 类继承体系

```
BasePredictionParser          ← 默认解析器，通用校验逻辑
  ├── GeminiParser            ← 补全 score_alt、reasoning→analysis 映射
  ├── DeepSeekParser          ← confidence_level→confidence 映射
  └── QwenParser              ← 中文 key 映射（结果/信心/分析）

SummaryParser                 ← 汇总输出专用解析器
```

### BasePredictionParser 校验规则

| 校验项 | 逻辑 | 失败处理 |
|---|---|---|
| `result` 合法性 | 必须为 `home_win`/`draw`/`away_win` 或中文映射 | 抛出 `ParseValidationError` → 重试 |
| 信心度归一化 | 限制在 1-10 范围内 | 自动修正 |
| 比分合理性 | 单方进球不超过 15 | 抛出 `ParseValidationError` → 重试 |
| `score_alt` 类型 | 确保 home/away 为 int，probability 在 0-1 | 自动修正 |
| `analysis` 空值 | 不允许为空 | 填充默认值 |

### 各模型 Parser 差异化处理

| Parser | 处理逻辑 |
|---|---|
| `GeminiParser` | 补全缺失的 `score_alt`（用主 score + 0.3 probability）；`reasoning` 字段映射到 `analysis` |
| `DeepSeekParser` | `confidence_level` 字段映射到 `confidence` |
| `QwenParser` | 中文 key 映射：`结果`→`result`、`信心`→`confidence`、`分析`→`analysis` |

### 自定义 Parser 扩展示例

```python
from app.services.prediction_parsers import BasePredictionParser, register_parser

class MyModelParser(BasePredictionParser):
    def parse(self, raw, model_name=""):
        # 自定义字段映射
        if "pred_result" in raw and "result" not in raw:
            raw["result"] = raw.pop("pred_result")
        return raw

# 注册后，model_name 包含 "mymodel" 的自动使用此 Parser
register_parser("mymodel", MyModelParser)
```

---

## 条件边：重试逻辑

`validate_outputs` 节点后的条件边 `_should_retry` 控制流程走向：

```python
def _should_retry(state: PredictionState) -> str:
    failed = state.get("failed", [])
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if failed and retry_count < max_retries:
        return "retry"      # → retry_failed 节点
    return "aggregate"      # → aggregate 节点
```

重试流程：
1. `validate_outputs` 标记校验失败的预测
2. 条件边判断：有失败 + 未超重试次数 → `retry_failed`
3. `retry_failed` 重新调用失败的模型
4. 重试后回到 `validate_outputs` 再次校验
5. 达到最大重试次数或全部通过 → `aggregate`

---

## 文件结构

```
server/app/services/
├── ai_predictor.py          # 入口：generate_predictions() / generate_single_match_predictions()
├── prediction_graph.py      # LangGraph StateGraph 定义 + 节点实现
└── prediction_parsers.py    # Output Parser 类 + 工厂函数 + 注册机制
```

### 与已有代码的关系

| 文件 | 变更 | 说明 |
|---|---|---|
| `ai_predictor.py` | 重写 | 函数签名不变，内部改用 LangGraph |
| `prediction_graph.py` | 新增 | LangGraph 流程编排 |
| `prediction_parsers.py` | 新增 | 可插拔输出解析器 |
| `admin.py` | 无变更 | API 接口兼容 |
| `scheduler.py` | 无变更 | 定时任务引用兼容 |
| `prompt_builder.py` | 无变更 | Prompt 构建复用 |
| `ofoxai.py` | 无变更 | LLM 调用客户端复用 |
| `requirements.txt` | 新增依赖 | `langgraph>=0.6.0` |

---

## Before vs After

| 维度 | Before | After |
|---|---|---|
| **并行** | 串行 for 循环，~40-60s/场 | `asyncio.gather` 并行，~5-8s/场 |
| **输出处理** | 硬编码 `_extract_json` | 可插拔 Parser 类，按模型差异化处理 |
| **校验** | 无 | result 合法性、信心度归一化、比分合理性 |
| **重试** | 无（单个模型失败只 log warning） | 条件边自动重试，最多 2 次 |
| **扩展性** | 改函数内部代码 | 新增节点+边 / 注册 Parser 类 |
| **汇总模型** | 硬编码 DeepSeek | State 中可配置 `summary_model_id` |
| **可观测性** | 只有 log 输出 | LangGraph 支持 mermaid 可视化 |

---

## 未来扩展方向

### 1. 多轮辩论节点

在 `validate_outputs` 和 `aggregate` 之间加入辩论节点：

```
[validate_outputs] → [debate_round] ──→ [aggregate]
                          ↑  ↓ (继续辩论)
                    [should_continue_debate]
```

持不同预测的模型互相挑战分析，DeepSeek 作为裁判最终裁决。

### 2. Checkpoint 持久化

LangGraph 支持 checkpoint，中断后可从任意节点恢复：

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as saver:
    graph = build_prediction_graph()
    app = graph.compile(checkpointer=saver)
    # 中断后可通过 thread_id 恢复
```

### 3. 更多 Parser

按需注册新模型的 Parser，例如：
- `ClaudeParser`：处理 Claude 特有的 XML 格式输出
- `GrokParser`：处理 Grok 的幽默风格输出
- `DoubaoParser`：处理豆包的特殊字段

### 4. LangGraph Studio 可视化

```python
# 生成 mermaid 流程图
graph = build_prediction_graph()
print(graph.get_graph().draw_mermaid())
```

可在 LangGraph Studio 中实时查看流程执行状态和节点数据。
