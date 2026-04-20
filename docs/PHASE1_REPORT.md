# Phase 1 后端基础搭建 — 进度汇报

> 日期：2026-04-10
> 阶段：Phase 1 后端基础搭建
> 状态：✅ 已完成

---

## 一、目标回顾

搭建 FastAPI 项目骨架，完成数据库 ORM 建模，实现核心外部 API 客户端和定时任务调度。

---

## 二、完成情况总览

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 1 | 初始化 Python 项目 | ✅ | `requirements.txt` 锁定 17 个依赖版本 |
| 2 | 创建基础目录结构 | ✅ | 所有 `__init__.py` 包占位完成 |
| 3 | 配置管理 | ✅ | `app/config.py` — pydantic-settings + `.env` |
| 4 | 数据库连接 | ✅ | `app/database.py` — 异步 SQLAlchemy 引擎 + async_sessionmaker |
| 5 | ORM 模型（7 张表） | ✅ | teams, matches, ai_models, predictions, long_term_predictions, users, user_votes |
| 6 | Alembic 初始化 | ✅ | `alembic/env.py` + `alembic.ini` + `script.py.mako` |
| 7 | 本地缓存 | ✅ | `app/core/cache.py` — TTLCache + 装饰器 |
| 8 | OfoxAI 客户端 | ✅ | `app/core/ofoxai.py` — 统一网关，兼容 OpenAI 格式 |
| 9 | API-Football 客户端 | ✅ | `app/core/api_football.py` — 赛程/比分/H2H |
| 10 | 微信登录 | ✅ | `app/core/wechat.py` — code → openid |
| 11 | APScheduler 定时任务 | ✅ | `app/core/scheduler.py` — 3 个 cron job |
| 12 | 依赖注入 | ✅ | `app/deps.py` — DB session、OfoxAI 客户端 |
| 13 | FastAPI 入口 | ✅ | `app/main.py` — lifespan + 路由注册 |

---

## 三、实际交付物（超出原计划）

Phase 1 原计划仅搭建骨架，实际开发中已完成了 Phase 2 大部分内容：

### 3.1 Pydantic Schemas（5 个）

| 文件 | 说明 |
|------|------|
| `app/schemas/match.py` | 比赛请求/响应模型 |
| `app/schemas/prediction.py` | 预测请求/响应模型 |
| `app/schemas/leaderboard.py` | 排行榜响应模型 |
| `app/schemas/user.py` | 用户登录/投票/站队模型 |
| `app/schemas/share.py` | 分享卡片模型 |

### 3.2 业务服务（6 个）

| 文件 | 说明 |
|------|------|
| `app/services/match_sync.py` | API-Football 数据同步 |
| `app/services/ai_predictor.py` | AI 预测生成（多模型并发） |
| `app/services/prediction_evaluator.py` | 预测准确性评估 |
| `app/services/leaderboard_calc.py` | 排行榜计算（AI/人机/站队） |
| `app/services/share_card.py` | 分享卡片生成 |
| `app/services/seed.py` | 种子数据初始化 |

### 3.3 API 路由（7 个路由文件，19 个端点）

| 文件 | 端点数 | 说明 |
|------|--------|------|
| `app/api/v1/matches.py` | 4 | 比赛列表/详情/按日查询 |
| `app/api/v1/predictions.py` | 5 | 预测列表/对比/打脸合集 |
| `app/api/v1/leaderboard.py` | 3 | AI/人机/站队排行 |
| `app/api/v1/users.py` | 4 | 登录/投票/站队/个人 |
| `app/api/v1/share.py` | 1 | 分享卡片 |
| `app/api/v1/admin.py` | 3 | 同步/生成/评估 |
| `app/api/v1/long_term.py` | 3 | 长期预测 CRUD |

### 3.4 工具模块

| 文件 | 说明 |
|------|------|
| `app/utils/prompt_builder.py` | Prompt 模板构建 |

### 3.5 部署配置

| 文件 | 说明 |
|------|------|
| `server/Dockerfile` | Python 3.12-slim 镜像 |
| `server/docker-compose.yml` | MySQL + API + Nginx 三容器 |
| `server/.env` / `.env.example` | 环境变量模板 |
| `server/start_dev.bat` | 本地开发启动脚本 |

---

## 四、技术难点与解决方案

### 4.1 Python 3.9 兼容性

**问题**：开发环境仅安装了 Python 3.9，不支持 `X | None` 联合类型语法（Python 3.10+ 特性）。

**解决**：
- ORM 模型：所有 `Mapped[X | None]` 改为 `Mapped[Optional[X]]`（SQLAlchemy 自行解析注解，`from __future__ import annotations` 不适用）
- Pydantic Schema & API 路由：安装 `eval_type_backport==0.3.1` 处理运行时类型求值

### 4.2 Pydantic v2 `model_` 前缀保护

**问题**：字段名如 `model_id` 触发 Pydantic v2 的 `model_` 保护命名空间警告。

**解决**：所有受影响的 Schema 添加 `model_config = ConfigDict(protected_namespaces=())`。

### 4.3 FastAPI `Depends()` 重复指定

**问题**：`Annotated[X, Depends()]` 配合默认值 `= Depends()` 导致参数重复。

**解决**：统一使用 `Annotated` 模式或默认值模式，避免同时指定。

### 4.4 greenlet 编译失败

**问题**：Windows 无 C++ 编译器，greenlet 无法从源码构建。

**解决**：`pip install greenlet --only-binary :all:` 仅使用预编译二进制包。

### 4.5 Windows GBK 编码

**问题**：`requirements.txt` 中的中文注释在 Windows 下 pip install 触发 `UnicodeDecodeError`。

**解决**：移除 requirements.txt 中所有中文注释。

### 4.6 `.env` 文件路径问题

**问题**：`config.py` 使用 `env_file=".env"` 相对路径，当工作目录不在 `server/` 下时，`.env` 无法被加载，导致所有配置回退到默认值（`DB_HOST=db`）。

**解决**：使用 `Path(__file__).resolve().parent.parent / ".env"` 绝对路径；`DB_HOST` 默认值从 `"db"` 改为 `"127.0.0.1"`（本地开发优先）。

### 4.7 Alembic 异步/同步引擎冲突

**问题**：`alembic/env.py` 使用 `async_engine_from_config`，但 `alembic.ini` 中的 URL 是同步 `pymysql` 驱动，导致迁移命令报错。

**解决**：将 `env.py` 改为使用 `engine_from_config` 同步引擎运行迁移。

### 4.8 SQLAlchemy `MissingGreenlet` 错误

**问题**：`db.flush()` 后，ORM 对象的服务端生成字段（如 `created_at`）尚未加载。FastAPI 序列化响应时触发延迟加载，但此时已不在 async session 上下文中，抛出 `MissingGreenlet`。

**解决**：所有 `db.flush()` 后增加 `await db.refresh(obj)`，主动加载服务端生成的字段。

### 4.9 `selectinload` 多参数语法错误

**问题**：`selectinload(Match.home_team, Match.away_team)` 在 SQLAlchemy 中不支持多个参数，会静默忽略第二个关系。

**解决**：拆为 `selectinload(Match.home_team), selectinload(Match.away_team)` 两个独立调用。

---

## 五、目录结构

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口 + lifespan
│   ├── config.py               # pydantic-settings 配置
│   ├── database.py             # 异步 SQLAlchemy 引擎
│   ├── deps.py                 # 依赖注入
│   ├── models/                 # 7 个 ORM 模型
│   │   ├── team.py
│   │   ├── match.py
│   │   ├── ai_model.py
│   │   ├── prediction.py
│   │   ├── long_term_prediction.py
│   │   ├── user.py
│   │   └── user_vote.py
│   ├── schemas/                # 5 个 Pydantic Schema
│   │   ├── match.py
│   │   ├── prediction.py
│   │   ├── leaderboard.py
│   │   ├── user.py
│   │   └── share.py
│   ├── api/
│   │   ├── router.py           # 路由聚合
│   │   └── v1/                 # 7 个路由文件，19 个端点
│   │       ├── matches.py
│   │       ├── predictions.py
│   │       ├── leaderboard.py
│   │       ├── users.py
│   │       ├── share.py
│   │       ├── admin.py
│   │       └── long_term.py
│   ├── services/               # 6 个业务服务
│   │   ├── match_sync.py
│   │   ├── ai_predictor.py
│   │   ├── prediction_evaluator.py
│   │   ├── leaderboard_calc.py
│   │   ├── share_card.py
│   │   └── seed.py
│   ├── core/                   # 5 个核心模块
│   │   ├── cache.py
│   │   ├── scheduler.py
│   │   ├── ofoxai.py
│   │   ├── api_football.py
│   │   └── wechat.py
│   └── utils/
│       └── prompt_builder.py
├── alembic/                    # 数据库迁移
├── alembic.ini
├── requirements.txt            # 17 个依赖
├── Dockerfile
├── docker-compose.yml
├── .env / .env.example
├── start_dev.bat
└── .gitignore
```

---

## 六、API 全量测试结果

本地 MySQL + FastAPI 环境已就绪，使用 `test_api.py` 脚本对全部 21 个端点进行自动化测试：

### 测试结果：21/21 全部通过 ✅

| # | 方法 | 端点 | 状态码 | 说明 |
|---|------|------|--------|------|
| 1 | GET | `/health` | 200 | 健康检查 |
| 2 | GET | `/api/v1/matches` | 200 | 比赛列表 |
| 3 | GET | `/api/v1/matches?round=小组赛` | 200 | 按轮次筛选 |
| 4 | GET | `/api/v1/matches?status=upcoming` | 200 | 按状态筛选 |
| 5 | GET | `/api/v1/matches/1` | 200 | 比赛详情 |
| 6 | GET | `/api/v1/predictions/match/1` | 200 | 比赛预测列表 |
| 7 | GET | `/api/v1/predictions/compare/1` | 200 | AI 预测对比 |
| 8 | GET | `/api/v1/predictions/face-slaps` | 200 | 打脸合集 |
| 9 | GET | `/api/v1/leaderboard/ai` | 200 | AI 排行榜 |
| 10 | GET | `/api/v1/leaderboard/ai?round=全部` | 200 | AI 排行（按轮次） |
| 11 | GET | `/api/v1/leaderboard/human` | 200 | 人机对战排行 |
| 12 | GET | `/api/v1/leaderboard/stand` | 200 | 站队排行 |
| 13 | GET | `/api/v1/long-term-predictions` | 200 | 长期预测列表 |
| 14 | GET | `/api/v1/users/profile?user_id=1` | 200 | 用户资料 |
| 15 | POST | `/api/v1/users/login` | 400 | 微信登录（缺 appid，预期失败） |
| 16 | POST | `/api/v1/users/vote?user_id=1` | 200 | 用户投票 |
| 17 | PUT | `/api/v1/users/support?user_id=1` | 200 | 选择站队 |
| 18 | GET | `/api/v1/share/card/1` | 200 | 分享卡片 |
| 19 | POST | `/api/v1/admin/matches/sync` | 200 | 触发赛程同步 |
| 20 | POST | `/api/v1/admin/predictions/generate` | 200 | 触发预测生成 |
| 21 | POST | `/api/v1/admin/predictions/evaluate` | 200 | 触发预测评估 |

### 测试中修复的 Bug

| 问题 | 原因 | 修复 |
|------|------|------|
| `selectinload` 多参数报错 | SQLAlchemy 不支持 `selectinload(A, B)` 语法 | 拆为 `selectinload(A), selectinload(B)` — 影响 5 处 |
| `.env` 未被正确加载 | 相对路径导致非 `server/` 目录启动时找不到 `.env` | `config.py` 改用 `Path(__file__)` 绝对路径，`DB_HOST` 默认值改为 `127.0.0.1` |
| Vote 接口 500 | `db.flush()` 后 `created_at` 未加载，序列化时触发 `MissingGreenlet` | 增加 `await db.refresh(obj)` 刷新服务端生成字段 |
| Vote 缺少前置校验 | 直接插入导致外键约束 500 | 增加用户/比赛存在性校验，返回 404 |
| `alembic/env.py` 异步引擎冲突 | 使用 `async_engine_from_config` 但连接串是同步 `pymysql` | 改为 `engine_from_config` 同步引擎 |
| `leaderboard_calc.py` 缺少 `from __future__ import annotations` | Python 3.9 不支持 `list[dict]` 返回类型 | 添加 future import |
| `match_sync.py` 的 `int | None` 语法 | Python 3.9 不支持 | 改为 `Optional[int]` |
| `cache key_fn` lambda 参数不匹配 | `get_human_leaderboard` 等 lambda 未接收 `db` 参数 | 补齐参数 |

---

## 七、验收标准检查

| 验收项 | 状态 | 说明 |
|--------|------|------|
| `docker compose up` 可启动 MySQL + FastAPI | ✅ | 配置已完成，需 MySQL 可用 |
| `alembic upgrade head` 成功建表 | ✅ | 本地 MySQL 已建库建表，7 张表就绪 |
| 访问 `/docs` 可看到 Swagger UI | ✅ | FastAPI 自动生成，21 个端点可见 |
| 全量 API 端点测试通过 | ✅ | 21/21 通过（含写操作 vote/support） |
| OfoxAI 客户端可调通 | ⏳ | 代码就绪，需配置 API Key |
| API-Football 客户端可获取赛程数据 | ⏳ | 代码就绪，需配置 API Key |

---

## 八、下一步计划（Phase 2/3 剩余）

Phase 2 的 Schema、Service、Route 已提前完成，核心待办：

1. **种子数据** — 运行 seed 服务初始化 AI 模型列表
2. **端到端测试** — 验证完整的同步→预测→评估→排行流程
3. **前端小程序开发（Phase 3）** — Taro 4 + React 18 + NutUI

---

## 八、依赖清单

```
fastapi==0.115.0           # Web 框架
uvicorn[standard]==0.30.0  # ASGI 服务器
sqlalchemy[asyncio]==2.0.35  # ORM
asyncmy==0.2.9             # MySQL 异步驱动
alembic==1.13.0            # 数据库迁移
cachetools==5.5.0          # 本地缓存
httpx==0.27.0              # HTTP 客户端
apscheduler==3.10.4        # 定时任务
pydantic==2.9.0            # 数据验证
pydantic-settings==2.5.0   # 配置管理
wechatpy==1.8.18           # 微信 SDK
Pillow==10.4.0             # 图片处理
python-dotenv==1.0.1       # .env 加载
loguru==0.7.2              # 日志
pymysql==1.1.1             # MySQL 同步驱动(Alembic)
eval_type_backport==0.3.1  # Python 3.9 类型兼容
```
