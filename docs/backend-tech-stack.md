# 后端技术栈整理（server/）

> 基于 `server/` 实际文件核对（requirements.txt / main.py / config.py / router.py / prediction_graph.py 等），非凭印象。

## 一、Web 框架 & 服务器

| 技术 | 版本 | 说明 |
|---|---|---|
| **FastAPI** | 0.115.0 | ASGI Web 框架，`lifespan` 管理启动/关闭，统一前缀 `/api/v1` |
| **uvicorn[standard]** | 0.30.0 | ASGI 服务器（Docker 内运行，绑 `127.0.0.1:8000`） |
| **CORS** | 内置 | `allow_origins=["*"]`，全开 |
| **StaticFiles** | 内置 | 挂载 `/static/avatars` 头像 + `/internal/odds` 私密赔率页 |

## 二、数据库 & ORM & 迁移

- **SQLAlchemy 2.0.35**（asyncio 模式）—— 核心 ORM，`async_session_factory`
- **Alembic 1.13.0** —— 数据库迁移（已累积 24 个版本脚本）
- **DB 驱动（按平台切换，见 `config.py:24`）**：
  - Linux/Docker → `asyncmy 0.2.9`（性能更好）
  - Windows 开发 → `aiomysql`（避开 `WinError 87`）
  - 同步（Alembic 用）→ `pymysql 1.1.1`
- **数据库**：远程阿里云 **MySQL**（`worldcup_prediction` 库），`.env` 配置
- 模型层 `app/models/`（18+ 张表），Schema 层 `app/schemas/`（14 个 Pydantic 校验）

## 三、数据校验 & 配置

- **Pydantic 2.9.0** + **pydantic-settings 2.5.0** —— 请求/响应序列化 + 配置管理
- **python-dotenv 1.0.1** —— 读 `.env`
- **eval_type_backport 0.3.1** —— 给 Python 3.9（Alembic venv）做类型注解兼容

## 四、认证 & 安全

- **python-jose[cryptography] 3.3.0** —— JWT（`SECRET_KEY` + 过期 720h/30天）
- **wechatpy 1.8.18** —— 微信小程序静默登录（`core/wechat.py`）
- `deps.py` 注入当前用户；`admin.py` 路由**目前无鉴权**（公网前需加令牌，已记录在案）

## 五、定时调度（APScheduler 3.10.4）

`core/scheduler.py` 定义每日管线：

- `00:30` 拉 Polymarket 市场
- `01:00` LangGraph 批量生成当天预测并落库
- `02:00` 同步积分榜/统计；`*/6h` 同步赔率
- `22:00` Telegram 推送当日预测+昨日赛果

## 六、AI 预测编排（项目核心特色）

- **LangGraph ≥0.6.0** —— `prediction_graph.py` 用 `StateGraph` 编排：`load_match → parallel_predict(asyncio.gather 并行) → validate → [失败 retry] → aggregate(汇总模型) → validate_summary`
- **OfoxAI 网关**（`openai>=1.50.0` 客户端，OpenAI 兼容协议）—— 统一调 10+ 个 LLM 模型；`DeepSeek` 作为汇总模型（保留兼容）
- `ai_predictor.py` / `prediction_parsers.py` / `prediction_evaluator.py` 配套

## 七、缓存

- **cachetools 5.5.0** —— **纯内存缓存**（无 Redis），`core/cache.py` + 启动 `cache_warmer` 预热；`/cache-stats`、`/cache/clear` 监控接口

## 八、外部数据集成（httpx 0.27.0 调用）

- **Highlightly API** —— 足球数据源（替代 API-Football），比赛/积分榜/统计同步
- **Polymarket** —— 预测市场（只读），经本机代理 `127.0.0.1:10808` 拉取，匹配本地比赛
- `core/highlightly.py` / `core/polymarket.py` / `core/ofoxai.py` 封装

## 九、通知 & 媒体

- **Telegram** —— `telegram_service.py` / `telegram_daily_push.py` / `telegram_formatter.py`（每日推送）
- **Pillow 10.4.0** —— 头像处理、`share_card.py` 分享图生成

## 十、日志 & 运维 & 部署

- **loguru 0.7.2** —— 全项目日志
- **Docker**（python:3.12-slim）+ **docker-compose**（mem_limit 400m，restart always）+ **nginx.conf** + `entrypoint.sh`（等 MySQL → `alembic upgrade` → 种子 → 启动）
- **压测**：locust 2.20.1 + gevent 23.9.1（`locustfile.py`）
- 表单上传：python-multipart 0.0.9

## 十一、分层结构（按职责）

```
app/
├── api/v1/   17 个路由(matches/leagues/predictions/leaderboard/odds/users/admin/polymarket…)
├── services/ 22 个服务(预测/赔率/积分榜/统计/h2h/同步/排行/VIP/Telegram…)
├── core/     基础设施(auth/cache/scheduler/wechat/highlightly/ofoxai/polymarket)
├── models/   SQLAlchemy ORM 表
├── schemas/  Pydantic 入参/出参
├── dml/      种子 SQL
└── utils/    prompt_builder 等
```

## 一句话总结

后端是一套 **「FastAPI + SQLAlchemy(async) + MySQL + Alembic」** 的经典异步 API 服务，最大特色是 **LangGraph 编排的多模型 AI 预测管线**，配合 **APScheduler 定时调度**、**OfoxAI 统一 LLM 网关**、**内存缓存**，外挂 Highlightly/Polymarket 数据源与 Telegram 推送，容器化部署在阿里云。
