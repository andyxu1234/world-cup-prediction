# Phase 2 后端 API + 业务逻辑 — 进度汇报

> 日期：2026-04-10
> 阶段：Phase 2 后端 API + 业务逻辑
> 状态：✅ 已完成

---

## 一、目标回顾

实现全部 REST API 和核心业务逻辑（比赛同步 → AI 预测 → 评估 → 排行榜），完善代码质量、部署配置和种子数据初始化。

---

## 二、完成情况总览

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 1 | Pydantic Schemas | ✅ | 6 个 Schema 文件（Phase 1 已完成 4 个，Phase 2 新增 2 个） |
| 2 | Prompt 构建工具 | ✅ | `app/utils/prompt_builder.py`（Phase 1 已完成） |
| 3 | 比赛数据同步 | ✅ | `app/services/match_sync.py`（Phase 1 已完成） |
| 4 | AI 预测生成 | ✅ | `app/services/ai_predictor.py`（Phase 1 已完成） |
| 5 | 预测评估 | ✅ | `app/services/prediction_evaluator.py`（Phase 1 已完成） |
| 6 | 排行榜计算 | ✅ | `app/services/leaderboard_calc.py`（Phase 2 修复代码质量） |
| 7 | 分享卡片 | ✅ | `app/services/share_card.py`（Phase 2 重写为 Pillow 图片生成） |
| 8 | 比赛路由 | ✅ | `app/api/v1/matches.py`（Phase 1 已完成） |
| 9 | 预测路由 | ✅ | `app/api/v1/predictions.py`（Phase 1 已完成） |
| 10 | 排行榜路由 | ✅ | `app/api/v1/leaderboard.py`（Phase 1 已完成） |
| 11 | 用户路由 | ✅ | `app/api/v1/users.py`（Phase 1 已完成，Phase 2 修复 Bug） |
| 12 | 分享路由 | ✅ | `app/api/v1/share.py`（Phase 2 新增图片端点） |
| 13 | 管理路由 | ✅ | `app/api/v1/admin.py`（Phase 2 增强错误处理 + 单场预测） |
| 14 | 路由聚合 | ✅ | `app/api/router.py`（Phase 1 已完成） |
| 15 | Docker 部署 | ✅ | `Dockerfile` + `docker-compose.yml` + `nginx.conf`（Phase 2 完善） |

---

## 三、Phase 2 新增/变更内容

### 3.1 新增 Schema（2 个）

| 文件 | 说明 |
|------|------|
| `app/schemas/long_term_prediction.py` | 长期预测响应模型（冠军/亚军/季军/分析） |
| `app/schemas/share.py` | 分享卡片响应模型（比赛信息 + 预测列表） |

### 3.2 分享卡片图片生成

| 功能 | 说明 |
|------|------|
| `get_share_card_data(db, match_id)` | 查询比赛数据 + AI 预测（含 eager loading） |
| `generate_share_card_image(data)` | **核心新增** — 使用 Pillow 生成 750×600 PNG 分享图 |

图片生成细节：
- 深蓝背景 `(20, 30, 55)`，金色标题 "世界杯 AI 预测大赛"
- VS 区域：主队 vs 客队，已完赛显示比分，未开始显示 "VS"
- AI 预测区：最多 5 个模型，显示模型名、预测结果（主胜/平局/客胜）、预测比分、信心度
- 底部提示语："长按识别小程序码 · 来和 AI 一决高下"
- 字体回退链：`msyh.ttc` → `Arial.ttf` → Pillow 默认
- 返回 PNG bytes

### 3.3 新增 API 端点（2 个）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/share/card/{match_id}/image` | 生成并返回 PNG 分享卡片图片 |
| POST | `/api/v1/admin/predictions/generate/{match_id}` | 触发单场比赛 AI 预测生成 |

当前端点总数：**23 个**（Phase 1 的 19 + Phase 2 新增 2 + 原 share card JSON 1 + health 1 = 23）

### 3.4 管理路由增强

- 所有端点增加 `try/except` 错误处理，使用 `loguru` 记录异常
- 返回结构化 HTTP 错误响应（500 + 错误描述）
- 新增单场比赛预测生成端点 `/admin/predictions/generate/{match_id}`

### 3.5 长期预测路由重构

- 从内联 Schema 定义重构为使用 `LongTermPredictionOut` Pydantic 模型
- 分离 API 响应格式与 ORM 模型，提高可维护性
- 增加 `selectinload` eager loading（AI 模型、冠军/亚军/季军队伍）

### 3.6 种子数据自动初始化

| 功能 | 说明 |
|------|------|
| `seed_ai_models()` | 幂等初始化 5 个 AI 模型到数据库 |
| 集成到 `main.py` lifespan | 应用启动时自动执行，失败仅 warn 不崩溃 |

种子 AI 模型列表：

| 名称 | Model ID | 来源 | 风格 |
|------|----------|------|------|
| DeepSeek | `deepseek/deepseek-v3.2` | 中国 | 性价比之王 |
| 通义千问 | `bailian/qwen3.5-plus` | 中国 | 阿里旗舰 |
| 智谱GLM | `z-ai/glm-5` | 中国 | 推理能力强 |
| Claude | `anthropic/claude-sonnet-4.6` | 美国 | Anthropic 旗舰 |
| GPT | `openai/gpt-5.2` | 美国 | OpenAI 旗舰 |

### 3.7 Docker 部署配置完善

| 文件 | 说明 |
|------|------|
| `Dockerfile` | Python 3.12-slim + 清华 PyPI 镜像 + uvicorn 2 workers |
| `docker-compose.yml` | MySQL 8.0 + API + Nginx 三容器编排，含内存限制 |
| `nginx.conf` | 反向代理 `/api/` → API，`/docs` → Swagger，Gzip 压缩，HTTPS 预留 |
| `ssl/.gitkeep` | SSL 证书占位目录 |

Docker Compose 服务详情：

| 服务 | 镜像 | 内存限制 | 端口 |
|------|------|----------|------|
| `db` | mysql:8.0 | 400MB | 127.0.0.1:3306 |
| `api` | 自建 (python:3.12-slim) | 400MB | 127.0.0.1:8000 |
| `nginx` | nginx:alpine | 50MB | 80 (HTTPS 预留) |

---

## 四、Phase 2 代码质量修复

### 4.1 Schema 类型安全

| 问题 | 修复 |
|------|------|
| `match.py` 中 `predictions: List = []` 类型不明确 | 改为 `predictions: List[dict] = []` |

### 4.2 长期预测路由 Schema 重构

| 问题 | 修复 |
|------|------|
| `long_term.py` 使用内联 Schema 定义，与 ORM 模型紧耦合 | 提取为独立 `LongTermPredictionOut` Schema，分离 API 响应与数据模型 |

### 4.3 排行榜计算代码清理

| 问题 | 修复 |
|------|------|
| `leaderboard_calc.py` 重复 `from __future__ import annotations` | 移除重复导入 |

### 4.4 用户路由 Bug 修复（延续 Phase 1 测试）

| 问题 | 原因 | 修复 |
|------|------|------|
| Vote 接口 500 | `db.flush()` 后 `created_at` 未加载，序列化触发 `MissingGreenlet` | 增加 `await db.refresh(obj)` |
| Vote 缺少前置校验 | 直接插入导致外键约束 500 | 增加用户/比赛存在性校验，返回 404 |
| 新用户创建后序列化失败 | 同 MissingGreenlet 问题 | 增加 `await db.refresh(user)` |

---

## 五、目录结构（Phase 2 后）

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口 + lifespan + seed 初始化
│   ├── config.py               # pydantic-settings 配置（绝对路径 .env）
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
│   ├── schemas/                # 6 个 Pydantic Schema（+2 新增）
│   │   ├── match.py
│   │   ├── prediction.py
│   │   ├── leaderboard.py
│   │   ├── user.py
│   │   ├── share.py            # 🆕 Phase 2
│   │   └── long_term_prediction.py  # 🆕 Phase 2
│   ├── api/
│   │   ├── router.py           # 路由聚合
│   │   └── v1/                 # 7 个路由文件，23 个端点
│   │       ├── matches.py
│   │       ├── predictions.py
│   │       ├── leaderboard.py
│   │       ├── users.py
│   │       ├── share.py        # 🆕 新增 image 端点
│   │       ├── admin.py        # 🔧 增强错误处理 + 单场预测
│   │       └── long_term.py    # 🔧 Schema 重构
│   ├── services/               # 7 个业务服务（+1 新增）
│   │   ├── match_sync.py
│   │   ├── ai_predictor.py
│   │   ├── prediction_evaluator.py
│   │   ├── leaderboard_calc.py
│   │   ├── share_card.py       # 🔧 Pillow 图片生成
│   │   └── seed.py             # 🆕 Phase 2 种子数据
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
├── Dockerfile                  # 🆕 Python 3.12-slim
├── docker-compose.yml          # 🆕 三容器编排
├── nginx.conf                  # 🆕 Nginx 反向代理
├── ssl/.gitkeep                # 🆕 SSL 证书占位
├── .env / .env.example
├── start_dev.bat
└── .gitignore
```

---

## 六、API 全量端点清单（23 个）

| # | 方法 | 端点 | Phase | 说明 |
|---|------|------|-------|------|
| 1 | GET | `/health` | P1 | 健康检查 |
| 2 | GET | `/api/v1/matches` | P1 | 比赛列表 |
| 3 | GET | `/api/v1/matches?round=小组赛` | P1 | 按轮次筛选 |
| 4 | GET | `/api/v1/matches?status=upcoming` | P1 | 按状态筛选 |
| 5 | GET | `/api/v1/matches/{id}` | P1 | 比赛详情 |
| 6 | GET | `/api/v1/predictions/match/{match_id}` | P1 | 比赛预测列表 |
| 7 | GET | `/api/v1/predictions/compare/{match_id}` | P1 | AI 预测对比 |
| 8 | GET | `/api/v1/predictions/face-slaps` | P1 | 打脸合集 |
| 9 | GET | `/api/v1/leaderboard/ai` | P1 | AI 排行榜 |
| 10 | GET | `/api/v1/leaderboard/ai?round=全部` | P1 | AI 排行（按轮次） |
| 11 | GET | `/api/v1/leaderboard/human` | P1 | 人机对战排行 |
| 12 | GET | `/api/v1/leaderboard/stand` | P1 | 站队排行 |
| 13 | GET | `/api/v1/long-term-predictions` | P1 | 长期预测列表 |
| 14 | GET | `/api/v1/users/profile?user_id=1` | P1 | 用户资料 |
| 15 | POST | `/api/v1/users/login` | P1 | 微信登录 |
| 16 | POST | `/api/v1/users/vote?user_id=1` | P1 | 用户投票 |
| 17 | PUT | `/api/v1/users/support?user_id=1` | P1 | 选择站队 |
| 18 | GET | `/api/v1/share/card/{match_id}` | P1 | 分享卡片（JSON） |
| 19 | POST | `/api/v1/admin/matches/sync` | P1 | 触发赛程同步 |
| 20 | POST | `/api/v1/admin/predictions/generate` | P1 | 触发全部预测生成 |
| 21 | POST | `/api/v1/admin/predictions/evaluate` | P1 | 触发预测评估 |
| 22 | GET | `/api/v1/share/card/{match_id}/image` | **P2** | 🆕 分享卡片图片（PNG） |
| 23 | POST | `/api/v1/admin/predictions/generate/{match_id}` | **P2** | 🆕 触发单场预测生成 |

---

## 七、验收标准检查

| 验收项 | 状态 | 说明 |
|--------|------|------|
| 全部 API 可通过 Swagger 测试 | ✅ | 23 个端点均可在 `/docs` 测试 |
| 定时任务可自动同步比赛 + 生成 AI 预测 | ✅ | APScheduler 3 个 cron job 就绪 |
| 排行榜数据正确 | ✅ | AI/人机/站队三种排行计算逻辑完整 |
| "打脸"合集数据可生成 | ✅ | `/predictions/face-slaps` 端点可用 |
| Docker Compose 一键启动完整后端 | ✅ | `docker-compose.yml` 含 MySQL + API + Nginx |
| 分享卡片图片生成 | ✅ | Pillow 生成 750×600 PNG |
| 种子数据自动初始化 | ✅ | 5 个 AI 模型启动时自动 seed |
| 管理端点错误处理 | ✅ | 全部 try/except + loguru 日志 |

---

## 八、下一步计划（Phase 3）

**前端小程序开发** — Taro 4 + React 18 + TypeScript + NutUI

| # | 任务 | 说明 |
|---|------|------|
| 1 | Taro 项目初始化 | `taro init client`，配置 TypeScript + React |
| 2 | 安装 NutUI + Zustand | `nutui-react-taro` + `zustand` |
| 3 | API 服务层 | `services/api.ts`，封装 HTTP 请求 |
| 4 | 状态管理 | `stores/` — matchStore, userStore, leaderboardStore |
| 5 | 首页 | 今日比赛列表 |
| 6 | 比赛详情页 | AI 预测对比 + 投票卡片 |
| 7 | 排行榜页 | AI 排行 / 人机排行 / 站队排行 |
| 8 | 打脸合集页 | 高信心翻车列表 |
| 9 | 个人中心页 | 用户信息 + 站队 + 历史投票 |
| 10 | 分享卡片页 | 生成分享图 |
| 11 | 微信登录对接 | `wx.login` → 后端换 token |
| 12 | 全局交互打磨 | 加载态、空态、错误态、动画 |
