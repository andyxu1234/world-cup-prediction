# AI 技术设计文档 · World Cup AI Prediction

> 面向「AI 应用开发 / AI Agent 方向」求职的技术设计文档
> 生成日期：2026-07-30
> 项目：基于多模型 LLM 的世界杯（足球）赛事预测系统

---

## 0. 写在前面（给招聘方 / 面试官）

这是一个**真实生产级**的 AI 应用项目，核心价值是：**把多个大模型对同一场比赛的预测，通过编排、汇总、评估，转化为可被用户消费的「AI 共识结论」+「模型排行榜」**。

我在项目里做的事情可以映射到两个求职方向：

- **AI 应用开发方向**：LLM 网关封装、Prompt 工程、结构化输出解析、多模型并行、RAG 式上下文注入、评估体系；
- **AI Agent 方向**：虽然当前是**确定性 LangGraph 流水线**（非自主 Agent），但已经具备「编排（Orchestration）+ 工具（`ofoxai`/`highlightly`/`polymarket` 客户端）+ 定时自主运行（Scheduler）+ 自动触达（Telegram）」的完整骨架，是向 ReAct / Tool-Use Agent 演进的天然土壤（详见第 6 节）。

---

## 1. 项目概览

| 维度 | 说明 |
|---|---|
| 产品形态 | 微信小程序 + 独立 Web/APK（去微信化中），前端 Taro/React，后端 FastAPI |
| 核心 AI 能力 | 多模型足球赛事预测、预测汇总（共识）、模型命中率排行、自动化推送 |
| 数据来源 | Highlightly（赛程/统计/赔率）、Polymarket（市场隐含概率）、API-Football（回退） |
| 模型调用 | 经 OfoxAI 统一网关（OpenAI 兼容协议），可热插拔任意模型 |
| 编排框架 | LangGraph（StateGraph 固定节点 + 条件边） |
| 自动化 | APScheduler 8 个定时任务（采集→预测→评估→推送） |
| 触达 | Telegram Bot（频道发帖 + 私聊/群广播） |

**业务闭环**：外部数据采集 → 数据库落库 → 定时（或手动）触发 LangGraph 预测 → 多模型并行预测 + 汇总 → 写入预测/汇总表 → 比赛结束后评估命中率 → 排行榜 → Telegram 自动推送结果。

---

## 2. 系统架构

```
┌──────────────────────────── 前端 (Taro / React) ────────────────────────────┐
│ 首页 / 比赛详情 / AI 模型详情 / 排行榜 / 投票                                    │
└───────────────┬───────────────────────────────────────────────────────────────┘
                │  HTTP / JSON
                ▼
┌──────────────────────────── 后端 FastAPI ───────────────────────────────────┐
│  /api/v1/*  (matches / predictions / leaderboard / admin / polymarket ...)    │
│                                                                               │
│  ┌── 调度层 (APScheduler) ────────────────────────────────────────────────┐  │
│  │  sync_matches(*/30) · generate_predictions(01:00) · sync_odds(*/6h) ·   │  │
│  │  sync_polymarket(00:30) · telegram_daily_push(22:00) · refresh_cache    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌── AI 预测编排 (LangGraph) ──────────────────────────────────────────────┐  │
│  │  load_match → parallel_predict → validate_outputs                       │  │
│  │                  ↑ (失败重试, ≤2)                                        │  │
│  │               aggregate → END                                           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│         │                  │                    │                            │
│         ▼                  ▼                    ▼                            │
│  OfoxAI 网关        Prompt Builder        Output Parsers                  │
│  (AsyncOpenAI)      (上下文拼装)           (模型专属解析/校验)              │
│         │                                                                │
│         ▼                                                                │
│  MySQL (matches / ai_models / predictions / prediction_summaries / ...)   │
│                                                                               │
│  ┌── 外部数据 / 触达 ─────────────────────────────────────────────────────┐  │
│  │  Highlightly · Polymarket Gamma · API-Football   →  Telegram Bot API   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. AI 能力总览（速查表）

| # | AI Skill | 技术实现 | 主要使用位置 | 解决的问题 |
|---|---|---|---|---|
| 1 | 统一 LLM 网关 | `OfoxAIClient`（AsyncOpenAI 封装，OpenAI 兼容协议） | `core/ofoxai.py` | 多模型统一接入、可热插拔、细粒度超时 |
| 2 | 预测流水线编排 | LangGraph `StateGraph` | `services/prediction_graph.py` | 多步骤有状态流程、失败重试、可观测 |
| 3 | 多模型并行预测 | `asyncio.gather(return_exceptions=True)` | `prediction_graph.parallel_predict` | 缩短总耗时、单模型失败不阻塞整体 |
| 4 | Prompt 工程 | `prompt_builder.py`（系统提示词 + 用户提示词模板） | `utils/prompt_builder.py` | 把结构化数据拼成模型可理解的预测指令 |
| 5 | 结构化输出解析 | `prediction_parsers.py`（按模型名分发 Parser） | `services/prediction_parsers.py` | 抹平不同模型 JSON 格式差异 |
| 6 | JSON 容错提取 | 5 级正则/截断修复策略 | `ofoxai._extract_json` | 兼容 markdown 包裹、截断、未闭合引号 |
| 7 | 预测汇总 / 共识 | 汇总模型（DeepSeek）综合多模型结论 | `prediction_graph.aggregate` | 生成「AI 共识」+ 备选比分 + 长文分析 |
| 8 | 超时与重试策略 | 120s read 超时 + 2 次重试 | `ofoxai.timeout` / `prediction_graph.retry_failed` | 慢模型/推理模型不拖垮整体 |
| 9 | Telegram 自动化触达 | Bot API 封装 + 定时推送 | `services/telegram_*` | 预测结果自动触达用户/频道 |
| 10 | 定时任务自动化 | APScheduler（8 个 cron 任务） | `core/scheduler.py` | 端到端无人值守运行 |
| 11 | 外部数据上下文注入 | Highlightly / Polymarket / API-Football 客户端 | `core/*` | 给模型提供实时赛程、统计、赔率、市场概率 |
| 12 | 预测评估与排行 | 命中率 SQL 聚合 + 排行榜计算 | `services/leaderboard_calc.py` | 量化每个模型准确性，形成「模型擂台」 |

---

## 4. AI 相关 Skill 详解（项目里用到哪里 · 解决什么问题）

### 4.1 统一 LLM 网关（OfoxAI）— *AI 应用开发核心*

- **位置**：`server/app/core/ofoxai.py` → `class OfoxAIClient`
- **实现**：基于 `openai.AsyncOpenAI`，`base_url` 指向 `https://api.ofox.io/v1`（OpenAI 兼容）。
  - 所有模型调用统一走这一个客户端：`predict_match(model, system_prompt, user_prompt)`。
  - 细粒度超时：`Timeout(connect=30, read=120, write=30, pool=10)`。
  - 模型温度覆盖表：`_MODEL_TEMPERATURE_OVERRIDES`（如 `moonshotai/kimi-k3` 强制 `temperature=1`，规避 400）。
- **解决的问题**：
  - **供应商解耦**：具体模型（DeepSeek / 通义千问 / Gemini / Claude / GPT / Kimi / MiniMax / Grok / 混元…）以 `model_id` 字符串标识，由数据库 `ai_models` 表驱动，**增删模型不改代码**。
  - **统一容错**：一处处理超时、重试、JSON 解析，上层编排无需关心底层网关细节。
- **简历话术**：*“设计了统一的 LLM 网关层，抽象 OpenAI 兼容协议，实现多模型热插拔与细粒度超时控制。”*

### 4.2 LangGraph 预测流水线编排

- **位置**：`server/app/services/prediction_graph.py`
- **实现**：`StateGraph(PredictionState)`，`PredictionState` 用 `TypedDict` 定义跨节点流转数据。
  - 节点：`load_match` → `parallel_predict` → `validate_outputs` →（`retry_failed` 条件回环）→ `aggregate` → `END`。
  - 条件边 `_should_retry`：校验失败且重试次数 < 2 则回到 `retry_failed`，否则进入 `aggregate`。
- **解决的问题**：
  - 把「加载数据 / 并行预测 / 校验 / 重试 / 汇总」拆成**有状态、可观测、可重入**的节点，比裸 `async` 函数更易维护与调试。
  - 状态在节点间用 `Annotated` reducer 合并，天然支持批量比赛 + 多模型。
- **简历话术**：*“使用 LangGraph 编排多步 AI 预测流程，通过状态图与条件边实现失败重试与汇总，保证长链路可观测。”*

### 4.3 多模型并行预测 + 容错

- **位置**：`prediction_graph.py` → `parallel_predict()`
- **实现**：
  ```python
  results = await asyncio.gather(
      *[_call_single_model(m) for m in models_to_predict],
      return_exceptions=True,   # 单模型异常不炸整体
  )
  ```
  每个模型在独立 `try/except` 内调用，失败项归入 `failed` 列表，成功项进入 `predictions`。
- **解决的问题**：
  - **延迟**：N 个模型并行，总耗时 ≈ 最慢一个，而非 N 倍累加。
  - **鲁棒性**：某个模型超时/报错，其余模型结果照常保留，后续由 `validate_outputs` + `retry_failed` 兜底。
- **简历话术**：*“基于 asyncio 的多模型并行推理，单模型失败隔离 + 全局重试，保障预测链路高可用。”*

### 4.4 Prompt 工程（上下文拼装）

- **位置**：`server/app/utils/prompt_builder.py`
- **实现**：
  - `SYSTEM_PROMPT`：资深足球分析专家，强制 JSON 输出。
  - `build_user_prompt()`：把**结构化业务数据**拼成模型可理解的预测指令——FIFA 排名、小组、赛季胜负平、主客场拆分、近 5 场状态、历史交锋、bet365 最新赔率，并附输出 JSON schema（`result / score / score_alt / confidence / analysis`）。
  - `build_summary_prompt()`：汇总专用，把多个模型的预测打包给「总编辑」模型。
  - 数据清洗细节：`_format_team_stats` 按当前联赛 + 当前/上赛季精确过滤（避免把友谊赛灌进去）；`_format_odds` 只取 bet365 最新快照。
- **解决的问题**：
  - 把「数据库里的统计」翻译成「模型能推理的上下文」，直接决定预测质量。
  - 通过「近 5 场」「主客场」「交锋」「赔率」多维度提示，引导模型做可解释判断，而非瞎猜。
- **简历话术**：*“负责 Prompt 工程，将结构化赛事数据（统计/交锋/赔率）转化为高质量预测指令，并设计汇总提示词实现多模型共识。”*

### 4.5 结构化输出解析与校验（模型专属 Parser）

- **位置**：`server/app/services/prediction_parsers.py`
- **实现**：可插拔 Parser 工厂 `get_parser(model_name)`：
  - `GeminiParser`：补默认 `score_alt`、把 `reasoning` 映射为 `analysis`（处理截断/特殊字段名）。
  - `DeepSeekParser`：`confidence_level` → `confidence`。
  - `QwenParser`：`结果/信心/分析` 中文 key → 英文字段。
  - `BasePredictionParser.validate()`：`result` 枚举校验、中文结果映射、`confidence` 归一 1–10、比分合理性（>15 判异常）、`score_alt` 概率 clamp。
- **解决的问题**：
  - **抹平模型差异**：不同厂商返回 JSON 的 key 名/结构不同，分层 Parser 让上层无需关心。
  - **数据质量门禁**：非法输出在 `validate` 阶段抛 `ParseValidationError`，触发重试，避免脏数据落库。
- **简历话术**：*“设计可插拔的输出解析层，按模型分发专属 Parser，统一校验 schema 与业务约束，保证结构化数据质量。”*

### 4.6 大模型 JSON 容错提取（5 级策略）

- **位置**：`ofoxai.py` → `OfoxAIClient._extract_json()` / `_repair_truncated_json()`
- **实现**：逐级尝试，直到成功或返回 `None`：
  1. 直接 `json.loads`；
  2. 提取 markdown ```json 代码块；
  3. 截取最外层 `{...}`；
  4. 修复未闭合引号 / 尾部多余逗号；
  5. 处理严重截断（按括号深度补全闭合符）。
- **解决的问题**：LLM 输出经常不标准——Gemini 易截断、Qwen 中文 key、Kimi 推理 token 占用输出窗口。这一层让**几乎所有“长 JSON 输出”都能被稳定解析**，是生产可用性的关键。
- **简历话术**：*“实现多级容错的 LLM JSON 提取与截断修复，显著提升非结构化输出的解析成功率。”*

### 4.7 预测汇总 / 共识生成（LLM-as-Aggregator）

- **位置**：`prediction_graph.py` → `aggregate()`
- **实现**：按 `match_id` 分组，合并「本次新预测 + 历史预测」，调用**汇总模型（默认 DeepSeek，特殊指定为“总编辑”）**生成：
  - 综合比分、备选比分、10 字短结论（`short_summary`）、100–200 字长文分析（`summary`）、综合信心（1–10）。
  - 写入 `prediction_summaries` 表，前端「AI 综合分析」卡片直接消费。
- **解决的问题**：
  - 单一模型有偏差，**多模型共识比单模型更稳**；用更强的模型做“编辑”综合各方观点，输出用户最终看到的结论。
  - 同时保留每个模型的独立预测，供「模型对比 / 排行榜」使用。
- **简历话术**：*“实现多模型预测汇总（LLM-as-aggregator），用强模型综合多观点生成共识结论，兼顾可解释性与准确性。”*

### 4.8 超时与重试策略

- **位置**：`ofoxai.py`（超时）、`prediction_graph.py`（`retry_failed` / `_should_retry`）
- **实现**：
  - 读超时 120s：慢模型（MiniMax / Gemini / Qwen 推理模型）及时失败，进入重试。
  - 重试：校验失败项最多重跑 2 次，重试时记录 DB / AI 耗时用于性能分析。
- **解决的问题**：生产环境里模型响应极不稳定，严格的超时 + 有界重试让**整体 SLA 可控**，不会因为一个卡死的请求拖垮一整批比赛。
- **简历话术**：*“设计 timeout + bounded retry 机制，保障多模型推理链路的 SLA 与可观测性。”*

### 4.9 Telegram 自动化触达

- **位置**：`services/telegram_service.py`、`telegram_daily_push.py`、`telegram_formatter.py`
- **实现**：
  - `TelegramService`：Bot API 封装，`send_message`（Markdown，解析失败降级纯文本重试）、`broadcast`（多 Chat 群发）、`send_to_public_channel`（频道发帖）。
  - `daily_push()`：22:00 推送今日比赛 + 预测 + 昨日赛果 +（周一）AI 排行榜到公共频道/监控群。
  - `telegram_formatter`：把数据格式化为 Markdown 卡片（共识、热门比分、命中率）。
- **解决的问题**：预测结果**自动、定时、格式化**触达用户，无需人工运营——这是「AI 应用」闭环的最后一公里。
- **简历话术**：*“基于 Telegram Bot 实现预测结果自动化推送与频道运营，含降级重试与多目标广播。”*

### 4.10 定时任务自动化（无人值守）

- **位置**：`core/scheduler.py` → `start_scheduler()`
- **实现**：`AsyncIOScheduler` 8 个 cron 任务：
  | 任务 | 频率 | 作用 |
  |---|---|---|
  | `sync_matches_and_respond` | */30min | 同步赛程 + 事件驱动下游 |
  | `generate_predictions` | 01:00 | 跑 LangGraph 生成预测 |
  | `sync_standings_and_stats` | 02:00 | 同步积分榜/统计 |
  | `sync_all_upcoming_odds` | */6h | 同步赔率 |
  | `sync_polymarket_events` | 00:30 | 拉取 Polymarket 胜负平 |
  | `sync_standalone_markets` | 03:00 | 拉取通用市场 |
  | `refresh_all_caches` | */5min | 缓存预热 |
  | `telegram_daily_push` | 22:00 | 推送 |
- **解决的问题**：把「采集 → 预测 → 评估 → 推送」串成**全自动数据管道**，生产环境零人工介入。
- **简历话术**：*“用 APScheduler 编排 8 个定时任务，构建端到端自动化的 AI 数据管道。”*

### 4.11 外部数据上下文注入（RAG 式）

- **位置**：`core/highlightly.py`、`core/polymarket.py`、`core/api_football.py`
- **实现**：
  - `HighlightlyClient`：赛程/比分/阵容/事件/统计/赔率/H2H；带浏览器 UA 绕过 Cloudflare，指数退避重试。
  - `polymarket.py`：只读 Gamma API，拉未来 7 天足球赛事的「胜负平」市场隐含概率（含代理出网）。
  - 这些数据在进入 `prompt_builder` 前落库，预测时作为**实时上下文**注入 prompt。
- **解决的问题**：LLM 没有实时赛事数据，必须**把外部权威数据喂给模型**才能做出有依据的预测（本质上是一种 RAG / 上下文增强）。
- **简历话术**：*“集成多家足球数据 API（Highlightly/Polymarket/API-Football），实现外部知识注入与代理出网，支撑模型推理。”*

### 4.12 预测评估与 AI 排行榜

- **位置**：`services/leaderboard_calc.py`、`telegram_daily_push.get_ai_leaderboard`
- **实现**：比赛结束后由 `prediction_evaluator` 标记 `is_correct_result / is_correct_score`；排行榜用 SQL `CASE` + `SUM` 聚合每个模型的胜负/比分命中率，按命中率排序。
- **解决的问题**：让系统**自我量化准确性**，形成「哪个 AI 模型更准」的透明榜单——这是产品的核心差异化卖点，也是模型选型的数据依据。
- **简历话术**：*“构建预测评估与模型排行榜体系，用命中率量化模型准确性，形成可解释、可迭代的反馈闭环。”*

---

## 5. AI 相关存储设计

| 表 | 作用 | 关键字段 |
|---|---|---|
| `ai_models` | 活跃模型清单（驱动并行预测） | `name`, `model_id`, `is_active` |
| `predictions` | 单模型单场预测 | `result`, `score_*`, `confidence`, `analysis`, `raw_response`, `is_correct_*` |
| `prediction_summaries` | 汇总共识 | `score_*`, `short_summary`, `summary`, `confidence` |
| `polymarket_*` | 市场隐含概率（只读参考） | `price`, `volume`, `liquidity` |

设计要点：`predictions` 上 `(match_id, model_id)` 唯一约束，保证幂等；`raw_response` 保留原始 JSON 便于复盘。

---

## 6. AI Agent 方向延展（面试加分项）

**诚实定位**：当前 AI 链路是**确定性 LangGraph 流水线**，不是自主 Agent——**没有工具调用（function calling / tool_use）、没有 ReAct、没有 LLM 自主决策分支**。模型只做「结构化预测」这一件事。

但项目已经具备向 Agent 演进的骨架：

1. **Orchestration 已就位**：LangGraph StateGraph 天然支持插入「规划 / 工具调用 / 反思」节点；
2. **Tools 已现成**：`ofoxai`（推理）、`highlightly`（查数据）、`polymarket`（查市场）、`telegram`（触达）都是可被 Agent 调用的「工具」；
3. **自主运行已具备**：Scheduler 可触发 Agent 周期巡检；
4. **可演进场景**：
   - 给汇总节点加上「如需更细数据，先调 Highlightly 拉最新统计」的 **tool-use 循环**；
   - 用 LLM 做**异常自检**：预测结果置信度过低时自动重写 prompt 重试（取代当前的固定 2 次重试）；
   - 把 Telegram 收消息做成 **command handler**，用户 `/predict 阿根廷 vs 法国` 即触发 Agent 编排。

> 在简历/面试里这样讲：`“我把多模型预测编排跑在 LangGraph 上，结构清晰、易扩展；下一步计划引入 tool-use，让编排具备自主调用数据/重试工具的能力，从确定性流水线升级为半自主 Agent。”`——既展示了落地能力，又体现了对 Agent 范式的理解。

---

## 7. 工程挑战与解决（展示工程深度）

| 挑战 | 现象 | 解决 |
|---|---|---|
| Windows 异步驱动连远程 MySQL | `asyncmy` 报 `WinError 87` | `config.py` 按平台切换 `aiomysql`/`asyncmy` |
| SSL 握手失败 | `'dict' object has no attribute 'wrap_bio'` | `connect_args["ssl"]` 改传 `ssl.SSLContext` 对象 |
| 事件循环不兼容 | `aiomysql` 报 `2003 Can't connect` | `main.py` 在 Windows 下切 `WindowsSelectorEventLoopPolicy` |
| 长耗时 LLM 调用期间 DB 连接被回收 | `2013 Lost connection` | LLM 调用前**关闭 DB session**，调用后再开短生命周期 session 读写 |
| 多模型输出格式各异 | JSON key/结构不一致 | 分层 Parser + 5 级容错提取 |

---

## 8. 技能清单速查（适合直接放简历）

**AI / LLM**
- 多模型 LLM 网关设计与封装（OpenAI 兼容协议）
- LangGraph 状态图编排（节点 + 条件边 + 重试）
- 多模型并行推理与容错（asyncio.gather + 隔离异常）
- Prompt 工程（结构化数据 → 预测指令 → 汇总共识）
- 结构化输出解析（模型专属 Parser + schema 校验）
- LLM JSON 容错提取与截断修复（5 级策略）
- LLM 输出评估与模型排行榜（命中率量化闭环）
- 外部知识注入 / RAG 式上下文增强（赛事数据 API）

**Agent / 自动化**
- APScheduler 端到端定时数据管道
- Telegram Bot 自动化触达（发帖/广播/降级重试）
- LangGraph → Tool-Use Agent 演进设计

**工程栈**
- Python / FastAPI / asyncio / SQLAlchemy(async) / MySQL
- Taro / React 小程序前端
- 日志可观测（loguru）、缓存预热、跨平台兼容

---

## 9. 关键文件索引

| 文件 | 职责 |
|---|---|
| `server/app/core/ofoxai.py` | 统一 LLM 网关 |
| `server/app/services/prediction_graph.py` | LangGraph 预测编排 |
| `server/app/utils/prompt_builder.py` | Prompt 工程 |
| `server/app/services/prediction_parsers.py` | 输出解析/校验 |
| `server/app/services/ai_predictor.py` | 预测入口（批量/单场） |
| `server/app/core/scheduler.py` | 定时任务 |
| `server/app/services/telegram_service.py` | Telegram 触达 |
| `server/app/services/leaderboard_calc.py` | AI 排行榜计算 |
| `server/app/core/highlightly.py` | 赛事数据客户端 |
| `server/app/core/polymarket.py` | 市场概率客户端 |
| `server/app/models/{ai_model,prediction,prediction_summary}.py` | AI 相关表模型 |
| `client/src/pages/{match-detail,ai-detail,leaderboard}/` | 前端 AI 展示 |
