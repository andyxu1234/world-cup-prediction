# 世界杯 AI 预测大赛 — 开发计划

## 总体策略

**先后端、再前端**：后端是数据基础，前端依赖 API。先确保数据流通，再打磨 UI。

## 里程碑总览

| 阶段 | 时间 | 目标 | 交付物 |
|------|------|------|--------|
| **P0 基础搭建** | 第 1-2 周 | 项目脚手架、数据库、Docker、API Key | 可运行的后端骨架 |
| **P1 核心功能** | 第 3-4 周 | 比赛同步、AI 预测生成、预测展示、排行榜 | 完整后端 API |
| **P2 用户功能** | 第 5-6 周 | 微信登录、投票、站队、人机排行 | 前端小程序 |
| **P3 传播功能** | 第 7-8 周 | 分享卡片、打脸合集、UI 打磨 | 可发布的小程序 |
| **P4 上线** | 第 9 周 | 内测、Bug 修复、小程序审核、正式上线 | 线上产品 |

---

## Phase 1: 后端基础搭建（1-2 天）

### 目标

搭建 FastAPI 项目骨架，完成数据库建表，实现核心外部 API 客户端。

### 目标目录结构

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 入口 + 生命周期
│   ├── config.py               # pydantic-settings 配置
│   ├── database.py             # SQLAlchemy 异步引擎
│   ├── deps.py                 # 依赖注入
│   ├── models/                 # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── team.py
│   │   ├── match.py
│   │   ├── ai_model.py
│   │   ├── prediction.py
│   │   ├── long_term_prediction.py
│   │   ├── user.py
│   │   └── user_vote.py
│   ├── schemas/                # Pydantic 请求/响应模型
│   ├── api/v1/                 # 路由层
│   ├── services/               # 业务逻辑
│   ├── core/                   # 核心模块
│   │   ├── cache.py            # 本地缓存
│   │   ├── scheduler.py        # APScheduler 定时任务
│   │   ├── ofoxai.py           # OfoxAI 统一网关客户端
│   │   ├── api_football.py     # API-Football 客户端
│   │   └── wechat.py           # 微信登录
│   └── utils/
│       └── prompt_builder.py   # Prompt 构建工具
├── alembic/                    # 数据库迁移
│   ├── env.py
│   └── versions/
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### 步骤

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1 | 初始化 Python 项目 | `requirements.txt` | 锁定所有依赖版本 |
| 2 | 创建基础目录结构 | 多个 `__init__.py` | 空包占位 |
| 3 | 配置管理 | `app/config.py` | pydantic-settings 读取 `.env` |
| 4 | 数据库连接 | `app/database.py` | 异步 SQLAlchemy 引擎 + session 工厂 |
| 5 | ORM 模型（7 张表） | `app/models/*.py` | teams, matches, ai_models, predictions, long_term_predictions, users, user_votes |
| 6 | Alembic 初始化 | `alembic/`, `alembic.ini` | 首次迁移脚本 |
| 7 | 本地缓存 | `app/core/cache.py` | cachetools TTLCache + 装饰器 |
| 8 | OfoxAI 客户端 | `app/core/ofoxai.py` | 统一网关，兼容 OpenAI 格式 |
| 9 | API-Football 客户端 | `app/core/api_football.py` | 赛程/比分/历史交锋 |
| 10 | 微信登录 | `app/core/wechat.py` | code 换 openid |
| 11 | APScheduler 定时任务 | `app/core/scheduler.py` | 比赛同步 + AI 预测 + 结果评估 |
| 12 | 依赖注入 | `app/deps.py` | DB session、当前用户、OfoxAI 客户端 |
| 13 | FastAPI 入口 | `app/main.py` | 注册路由 + 生命周期（启动定时任务） |

### 验收标准

- [ ] `docker compose up` 可启动 MySQL + FastAPI
- [ ] `alembic upgrade head` 成功建表
- [ ] 访问 `/docs` 可看到 Swagger UI
- [ ] OfoxAI 客户端可调通（手动测试一个模型）
- [ ] API-Football 客户端可获取赛程数据

---

## Phase 2: 后端 API + 业务逻辑（2-3 天）

### 目标

实现全部 REST API 和核心业务逻辑（比赛同步 → AI 预测 → 评估 → 排行榜）。

### 步骤

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1 | Pydantic Schemas | `app/schemas/*.py` | match, prediction, leaderboard, user, share |
| 2 | Prompt 构建工具 | `app/utils/prompt_builder.py` | 统一 Prompt 模板，注入球队/交锋数据 |
| 3 | 比赛数据同步 | `app/services/match_sync.py` | 调 API-Football → 更新 matches/teams 表 |
| 4 | AI 预测生成 | `app/services/ai_predictor.py` | 遍历未预测比赛 → 调 OfoxAI → 存 predictions |
| 5 | 预测评估 | `app/services/prediction_evaluator.py` | 比赛结束 → 计算正确性 → 更新 is_correct_* |
| 6 | 排行榜计算 | `app/services/leaderboard_calc.py` | AI 排行 / 人机排行 / 站队排行 |
| 7 | 分享卡片 | `app/services/share_card.py` | 生成分享卡片数据（Pillow 绘图） |
| 8 | 比赛路由 | `app/api/v1/matches.py` | GET /matches, GET /matches/:id |
| 9 | 预测路由 | `app/api/v1/predictions.py` | GET /matches/:id/predictions, GET /predictions/face-slaps |
| 10 | 排行榜路由 | `app/api/v1/leaderboard.py` | GET /leaderboard/ai, /human, /stand |
| 11 | 用户路由 | `app/api/v1/users.py` | POST /login, POST /vote, PUT /support, GET /profile |
| 12 | 分享路由 | `app/api/v1/share.py` | GET /share/card/:matchId |
| 13 | 管理路由 | `app/api/v1/admin.py` | POST /matches/sync, /predictions/generate, /predictions/evaluate |
| 14 | 路由聚合 | `app/api/router.py` | 统一注册所有 v1 路由 |
| 15 | Docker 部署 | `Dockerfile`, `docker-compose.yml` | 一键部署 |

### 验收标准

- [ ] 全部 API 可通过 Swagger 测试
- [ ] 定时任务可自动同步比赛 + 生成 AI 预测
- [ ] 排行榜数据正确（手动验证几场）
- [ ] "打脸"合集数据可生成
- [ ] Docker Compose 一键启动完整后端

---

## Phase 3: 前端小程序（3-4 天）

### 目标

基于高保真设计稿 `docs/ui-design.html`，开发完整微信小程序。

### 技术栈

- Taro 4 + React 18 + TypeScript
- NutUI (京东) 组件库
- Zustand 状态管理

### 步骤

| # | 任务 | 说明 |
|---|------|------|
| 1 | Taro 项目初始化 | `taro init client`，配置 TypeScript + React |
| 2 | 安装 NutUI + Zustand | `nutui-react-taro` + `zustand` |
| 3 | API 服务层 | `services/api.ts`，封装 http 请求 |
| 4 | 状态管理 | `stores/` — matchStore, userStore, leaderboardStore |
| 5 | 首页 | 今日比赛列表，参照 ui-design Index 页 |
| 6 | 比赛详情页 | AI 预测对比 + 投票卡片，参照 Match Detail 页 |
| 7 | 排行榜页 | AI 排行 / 人机排行 / 站队排行，参照 Leaderboard 页 |
| 8 | 打脸合集页 | 高信心翻车列表，参照 Face Slap 页 |
| 9 | 个人中心页 | 用户信息 + 站队 + 历史投票，参照 Profile 页 |
| 10 | 分享卡片页 | 生成分享图，参照 Share Card 页 |
| 11 | 微信登录对接 | `wx.login` → 后端换 token |
| 12 | 全局交互打磨 | 加载态、空态、错误态、动画 |

### 验收标准

- [ ] 6 个页面全部可正常访问和交互
- [ ] 微信登录正常
- [ ] 投票 + 站队功能正常
- [ ] 分享卡片可生成并分享
- [ ] UI 还原度 > 90%（参照 ui-design.html）

---

## Phase 4: 部署 + 联调 + 上线（1-2 天）

### 目标

部署到阿里云 ECS，前后端联调，提交小程序审核。

### 步骤

| # | 任务 | 说明 |
|---|------|------|
| 1 | 阿里云 ECS 部署 | Docker Compose 启动后端 |
| 2 | Nginx 配置 | 反向代理 + SSL + 静态资源 |
| 3 | 前后端联调 | 逐页面验证 API 数据和交互 |
| 4 | 种子数据 | 手动同步几场比赛 + 生成 AI 预测，确保有展示数据 |
| 5 | 小程序审核提交 | 微信后台提交审核 |
| 6 | Bug 修复 | 内测反馈问题修复 |

### 验收标准

- [ ] 线上环境可正常访问
- [ ] 全部 API 响应正常
- [ ] 小程序审核通过

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| OfoxAI API 不稳定 | AI 预测生成失败 | 加入重试机制（3 次），失败后跳过该模型 |
| API-Football 免费额度不足 | 比赛数据同步中断 | 控制同步频率（每日 1-2 次），必要时升级付费 |
| 小程序审核被拒 | 上线延迟 | 提前了解审核规范，避免敏感内容 |
| 2 核 2G 内存不足 | 服务不稳定 | 监控内存，必要时扩容到 4G |
| 世界杯开赛前未完成 | 错过最佳时机 | 优先保证核心功能（预测+排行），其余迭代 |
