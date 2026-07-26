# 技术栈全景（world-cup-prediction）

> 项目定位：微信小程序（Taro/React）+ FastAPI 后端，用 LangGraph 编排 10+ 主流大模型对足球赛事做 AI 预测，接入赔率 / Polymarket 预测市场信号，含排行榜、数据中心、VIP；后端 Python 3.12 / 异步 SQLAlchemy / MySQL，Docker 部署。

---

## 一、前端（微信小程序 + 跨端）

| 技术 | 版本 | 用途 |
|---|---|---|
| Taro | 4.1.11 | 跨端框架，一份代码编译到 微信 / 支付宝 / 百度 / 头条 / H5（`build:weapp` / `alipay` / `h5` …） |
| React | 18.3 | UI 层（函数组件 + Hooks） |
| React DOM | 18.3 | Web / H5 渲染 |
| TypeScript | 5.4 | 全量类型（templateInfo 已开 `typescript: true`） |
| Sass | 1.77 | 样式（`.scss`，模块化样式表） |
| Zustand | 4.5 | 轻量状态管理（模块化 store，客户端复合排序） |
| Babel + Webpack 5 | 5.91 | Taro 内置构建链路（react-refresh / prebundle） |

平台以**微信小程序为主**，踩过 iOS 原生视图、`sofifa` 防盗链 403、Taro GET 数组序列化 422 等跨端坑。

## 二、后端（API 服务）

| 技术 | 版本 | 用途 |
|---|---|---|
| FastAPI | 0.115 | ASGI Web 框架，50+ 端点，`/api/v1` 聚合路由 |
| Uvicorn | 0.30 | ASGI 服务器（`[standard]` 含 uvloop / websockets） |
| Pydantic | 2.9 | 请求 / 响应数据校验 |
| pydantic-settings | 2.5 | 配置管理（`.env` 驱动） |
| python-multipart | 0.0.9 | 表单 / 文件上传 |

## 三、数据层

| 技术 | 版本 | 用途 |
|---|---|---|
| SQLAlchemy | 2.0.35 `[asyncio]` | 异步 ORM（2.0 风格，依赖注入 `get_db`） |
| asyncmy | 0.2.9 | 异步 MySQL 驱动（注：Windows 连远程库会 `WinError 87`，生产用 Linux） |
| pymysql | 1.1.1 | 同步驱动，专供 alembic 迁移用 |
| Alembic | 1.13 | 数据库迁移（幂等 DDL） |
| MySQL | — | 关系库（远程阿里云 `47.101.167.103`），18 张表 |

## 四、AI / Agent 核心 ⭐

| 技术 | 版本 | 用途 |
|---|---|---|
| LangGraph | ≥0.6 | 有状态多智能体编排（节点：load → 并行预测 → 校验 → 条件边重试 → 汇总） |
| OpenAI SDK | ≥1.50 | 统一网关调 10+ 模型（兼容 OfoxAI `api.ofox.io`，`AsyncOpenAI`） |
| 模型阵容 | — | DeepSeek / Claude / GPT / Gemini / Qwen / Kimi … 由 `ai_models` 表 DB 驱动、可插拔 |

## 五、调度 / 自动化

| 技术 | 版本 | 用途 |
|---|---|---|
| APScheduler | 3.10 | 6 个 cron 任务（比赛同步 / 预测生成 / 统计 / 缓存预热 / 赔率 / Polymarket） |

## 六、缓存 / 网络 / 工具

| 技术 | 版本 | 用途 |
|---|---|---|
| cachetools | 5.5 | `TTLCache` 内存缓存（两类 + 每 5 分预热） |
| httpx | 0.27 | 异步 HTTP 客户端（调外部 API、Polymarket 代理） |
| wechatpy | 1.8.18 | 微信小程序 / 公众号 SDK |
| python-jose | 3.3 `[cryptography]` | JWT 鉴权 |
| loguru | 0.7.2 | 结构化日志 |
| Pillow | 10.4 | 头像代理 / 图像处理 |
| python-dotenv | 1.0.1 | 环境变量加载 |
| eval_type_backport | 0.3.1 | Python 3.9 类型注解兼容 |

## 七、测试 / 压测

| 技术 | 版本 | 用途 |
|---|---|---|
| locust | 2.20 | 负载测试 |
| gevent | 23.9.1 | 协程支撑（locust 依赖） |

> ⚠️ 说明：项目目前**没有 pytest 单测 / CI**（仅 2 个近乎空的测试文件），在面试里要主动承认是待补短板，反而显诚实。

## 八、部署 / 运维

| 技术 | 用途 |
|---|---|
| Docker + Docker Compose | 容器化（`python:3.12-slim`，`entrypoint.sh`：等 MySQL → `alembic upgrade` → 种子 → 启动） |
| Nginx | 反代 + HTTPS + 健康检查（见 `DEPLOYMENT.md`） |
| 阿里云 MySQL | 远程生产库 |

---

## 面试展开建议

### 偏 AI Agent 岗（重点 3 条）
1. **LangGraph 有状态多模型流水线**：`prediction_graph.py` 把"多模型并行预测 → 校验 → 失败重试 → 汇总共识"建模成 StateGraph；`PredictionState` TypedDict 在节点间流转，条件边 `_should_retry` 控制最多重试 2 次，单模型挂不影响整体（`asyncio.gather(return_exceptions=True)`）。
2. **LLM 输出不可信的工程化处理**：`ofoxai._extract_json` / `_repair_truncated_json` 写 5 级容错解析（纯 JSON → 代码块 → 最外层 `{}` → 截断引号/逗号修复 → 按括号深度裁剪补全），配 `prediction_parsers` 各厂商子类适配，校验失败才进图内重试。
3. **候选集约束防幻觉匹配**：`polymarket_match.py` 代码先按联赛 + 时间窗(±3 天)捞候选 `match_id`，只把候选喂给 DeepSeek 选，校验层拦截越界/幻觉 id。

### 偏全栈岗（重点 3 条）
1. **完整产品全栈 ownership**：前端 Taro/React + 后端 FastAPI + MySQL + Docker，从 0 到 1 覆盖 15 个小程序页面、50 个 API 端点、18 张表。
2. **异步后端架构**：SQLAlchemy 2.0 async + `asyncmy`；连接池 `pool_size=5/max_overflow=10/pool_recycle=3600` + `pool_pre_ping`；`match_odds` 用 `snapshot_date` + `snapshot_hour` 双字段做赔率快照桶。
3. **影子库零停机迁移**：大 schema 改造先建影子库复制验证，低峰期 `alembic upgrade head` + 发布，附 `downgrade` / 备份回滚预案。

### 两个岗位都能讲的通用牌
- **微信 6.1.5 合规整改**：因"彩票预测/竞猜"违规，下架投票/下注、AI 转只读分析、敏感词替换 —— 体现产品/法规意识。
- **缓存层**：TTLCache 两类缓存 + 每 5 分预热，减 DB 压力。
- **部署成熟度**：Docker Compose + Nginx 反代 + HTTPS + 容器启动自动迁移 + 健康检查。

## 诚实提醒（面试官可能追问的薄弱点，提前准备）
1. **无自动化测试 / CI**：被问到就说"靠日志 + 手动验证，这是我明确要补的短板"。
2. **admin 路由无鉴权**：是内部运维接口，公网部署前必加令牌闸（可接"我的安全意识 + 整改计划"）。
3. **无 RAG / 向量库**：上下文是 DB 查询直接拼 prompt，即查即用的上下文注入，别硬凑 RAG。
4. **README 与代码略有出入**：README 写 5 个 cron / odds 每日 04:00，代码实际 6 个、odds 每 6h —— 面试以代码为准。
5. **`season=2026` 硬编码**在 Polymarket 匹配里，是已知技术债务。
