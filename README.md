# 🏆 AI 预测世界杯

让多个 AI 大模型同台竞技，预测足球比赛（世界杯及多国主流联赛）结果。用户可以围观 AI 预测、参与投票、与 AI 一较高下，并通过社交分享扩大传播。

**开源地址**: [https://github.com/AndyXu-Citi/world-cup-prediction](https://github.com/AndyXu-Citi/world-cup-prediction)

## 产品亮点

- **AI 对决**：10+ 个主流 AI 模型同台预测，看谁更准（阵容由数据库 `ai_models` 表驱动，可随时增删改）
- **多联赛**：不止世界杯，已支持英超、西甲、德甲、意甲、法甲、欧冠、欧联等联赛，数据中心按联赛切换视角
- **人机大战**：用户投票预测（胜负 + 精确比分），与 AI 模型一较高下
- **排行榜**：AI 排行榜 / 人类排行榜双维度，胜负命中率 & 比分命中率独立统计，支持多联赛筛选
- **数据中心**：积分榜 + 球员榜（射手/助攻/牌），按联赛切换
- **赔率数据**：接入博彩公司赛前赔率快照，支持赔率走势与按结果（胜平负）聚合
- **VIP 会员**：支持按月/季/年/永久会员套餐，提供会员权益与管理后台
- **分享传播**：支持分享给好友和分享到朋友圈
- **AI 综合分析**：多模型预测聚合为共识结论 + 信心指数（LangGraph 编排）
- **趣闻生成**（历史功能）：曾基于用户战绩动态生成足球小知识

## 技术架构

```
微信小程序 (Taro + React + SCSS)
         │
         ▼
    FastAPI (Python 3.12 + Uvicorn)
    ├── REST API (50 个端点 / 13 个路由模块)
    ├── APScheduler 定时任务 (5 个 cron job)
    ├── LangGraph + OfoxAI 统一网关 (AI 模型编排)
    ├── Highlightly 比赛 / 积分榜 / 球员 / 赔率 数据源
    └── cachetools TTLCache 本地缓存
         │
         ▼
    MySQL 8.0 (asyncmy 异步驱动)

外部依赖：
  ├── OfoxAI  (https://api.ofox.io/v1) — AI 模型统一网关
  └── Highlightly (https://soccer.highlightly.net) — 足球数据（比赛/积分榜/球员/赔率）
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 小程序前端 | Taro 4.1 + React 18 + TypeScript + Zustand + SCSS |
| 后端框架 | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| 数据库 | MySQL 8.0 (asyncmy) |
| 缓存 | cachetools TTLCache（只读 + 用户两类缓存） |
| 定时任务 | APScheduler |
| HTTP 客户端 | httpx (async) |
| AI 编排 | LangGraph `StateGraph` + OfoxAI（OpenAI 兼容 `AsyncOpenAI` 客户端） |
| 比赛数据 | Highlightly（替代原 API-Football） |
| 图片处理 | Pillow（分享卡片 / 头像处理） |
| 认证 | JWT + 微信静默登录 |
| 部署 | Docker Compose + Nginx |

## 项目结构

```
world-cup-prediction/
├── client/                          # Taro 小程序前端
│   ├── src/
│   │   ├── app.config.ts            # 页面路由 & TabBar 配置 (15 个注册页面)
│   │   ├── app.ts                   # 应用入口 (微信静默登录)
│   │   ├── assets/                  # 静态资源 (图标/SVG/收款码)
│   │   ├── pages/                   # 页面目录 (15 个注册页面)
│   │   ├── services/api.ts          # 后端 API 封装
│   │   ├── stores/index.ts          # Zustand 状态管理
│   │   └── styles/                  # 全局样式 & 变量
│   └── config/                      # Taro 构建配置
│
├── server/                          # FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # 入口 + 生命周期
│   │   ├── config.py                # Pydantic Settings 配置
│   │   ├── database.py              # SQLAlchemy 异步引擎
│   │   ├── deps.py                  # 依赖注入
│   │   ├── models/                  # ORM 模型 (18 张表 / 19 个类)
│   │   ├── schemas/                 # Pydantic 模型 (14 个)
│   │   ├── api/
│   │   │   ├── router.py            # 路由聚合 (前缀 /api/v1)
│   │   │   └── v1/                  # 路由模块 (13 个有效模块)
│   │   │       ├── matches.py / leagues.py / predictions.py
│   │   │       ├── leaderboard.py / standings.py / users.py
│   │   │       ├── admin.py / long_term.py / cn_mapping.py
│   │   │       ├── data.py / teams.py / players.py / proxy.py
│   │   │       └── (fun_fact.py / share.py / round_translations.py 为空，历史遗留)
│   │   ├── services/                # 业务逻辑 (16 个)
│   │   │   ├── sync_pipeline.py     # 数据同步编排（事件驱动）
│   │   │   ├── match_sync.py        # 比赛数据同步 (Highlightly)
│   │   │   ├── stats_sync.py        # 球队统计同步
│   │   │   ├── player_stats_sync.py # 球员盒子分同步
│   │   │   ├── standings_sync.py    # 官方积分榜同步
│   │   │   ├── h2h_sync.py          # 历史交锋同步
│   │   │   ├── odds_service.py      # 赔率同步（追加式每日快照）
│   │   │   ├── ai_predictor.py      # AI 预测服务
│   │   │   ├── prediction_graph.py  # LangGraph 预测编排图
│   │   │   ├── prediction_parsers.py# LLM 输出解析（多模型适配）
│   │   │   ├── prediction_evaluator.py # 预测准确性评估
│   │   │   ├── leaderboard_calc.py  # 排行榜计算
│   │   │   ├── standings_calc.py    # 积分榜现算（回退）
│   │   │   ├── vip_service.py       # VIP 会员服务
│   │   │   ├── share_card.py        # 分享卡片图片生成 (空实现/历史)
│   │   │   └── seed.py              # 种子数据 (空)
│   │   ├── core/                    # 核心模块
│   │   │   ├── ofoxai.py            # OfoxAI 网关 (AsyncOpenAI)
│   │   │   ├── highlightly.py       # Highlightly 数据客户端
│   │   │   ├── wechat.py            # 微信登录
│   │   │   ├── scheduler.py         # 定时任务调度 (5 job)
│   │   │   ├── cache.py             # 缓存封装 (TTLCache)
│   │   │   ├── cache_warmer.py      # 缓存预热
│   │   │   ├── auth.py              # JWT 认证
│   │   │   └── api_football.py      # 历史遗留客户端 (已弃用)
│   │   └── utils/prompt_builder.py  # LLM Prompt 模板
│   ├── alembic/                     # 数据库迁移 (17 个版本)
│   ├── static/                      # 头像 / 代理缓存静态目录
│   ├── start.sh / stop.sh / restart.sh  # 服务管理脚本
│   ├── docker-compose.yml           # Docker 编排
│   ├── Dockerfile
│   └── requirements.txt
│
└── docs/                            # 项目文档
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.0
- Docker & Docker Compose (可选，推荐)

### 本地开发

```bash
# ====== 后端 ======
cd server

# 创建虚拟环境 & 安装依赖
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt --loglevel verbose

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入数据库密码、OfoxAI Key、Highlightly Key、微信 AppID 等

# 创建数据库
python -c "
import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='你的密码')
cur = conn.cursor()
cur.execute('CREATE DATABASE IF NOT EXISTS worldcup_prediction CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
conn.commit()
conn.close()
"

# 数据库迁移
alembic revision --autogenerate -m "init"
alembic upgrade head

# 启动后端
uvicorn app.main:app --reload --port 8000
# 或使用管理脚本: ./start.sh (后台运行)

# Swagger UI: http://localhost:8000/docs


# ====== 前端 (另开终端) ======
cd ../client
npm install --loglevel verbose

# H5 浏览器预览 (热更新)
npm run dev:h5
# 访问 http://localhost:10088

# 微信开发者工具预览
npm run dev:weapp
# 在微信开发者工具中打开 dist/

# 生产构建
npm run build:weapp
```

> **注意**：
> - H5 模式需确保后端已配置 CORS（`server/app/main.py` 已添加）
> - 微信开发者工具需勾选「不校验合法域名」
> - `--loglevel verbose` 参数可显示 npm 安装详细进度

### 服务管理脚本 (server/)

| 脚本 | 用途 |
|------|------|
| `./start.sh` | 后台启动服务 (nohup)，日志输出到 `/tmp/worldcup-server.log` |
| `./stop.sh` | 停止 uvicorn 进程 |
| `./restart.sh` | 先 stop 再 start |

使用前请确保脚本有执行权限：
```bash
chmod +x start.sh stop.sh restart.sh
```

### Docker 部署

```bash
cd server
cp .env.example .env
docker compose up -d
docker compose exec api alembic upgrade head
docker compose logs -f api
```

详见 [部署指南](docs/DEPLOYMENT.md)。

## 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `DB_PASSWORD` | MySQL 密码 | 是 |
| `DB_HOST` | 数据库地址 (本地 127.0.0.1，Docker 用 db) | 否 (默认 127.0.0.1) |
| `DB_PORT` | 数据库端口 | 否 (默认 3306) |
| `DB_NAME` | 数据库名 | 否 (默认 worldcup_prediction) |
| `DB_USER` | 数据库用户 | 否 (默认 root) |
| `OFOXAI_API_KEY` | OfoxAI 统一网关密钥 | 是 |
| `OFOXAI_BASE_URL` | OfoxAI 网关地址 | 否 (默认 `https://api.ofox.io/v1`) |
| `HIGHLIGHTLY_API_KEY` | Highlightly 比赛数据 API Key | 是 (无则无法同步数据) |
| `HIGHLIGHTLY_BASE_URL` | Highlightly 网关地址 | 否 (默认 `https://soccer.highlightly.net`) |
| `HIGHLIGHTLY_LEAGUE_ID` | 默认回退联赛 ID (世界杯) | 否 (默认 1635) |
| `HIGHLIGHTLY_SEASON` | 默认回退赛季 | 否 (默认 2026) |
| `WECHAT_APP_ID` | 微信小程序 AppID | 是 |
| `WECHAT_APP_SECRET` | 微信小程序 AppSecret | 是 |
| `SECRET_KEY` | JWT 签名密钥 (生产环境必须修改) | 否 (有默认值) |
| `TOKEN_EXPIRE_HOURS` | JWT 有效期(小时) | 否 (默认 720 / 30 天) |
| `AVATAR_BASE_URL` | 头像访问基础路径 (如 `https://域名/static/avatars/`) | 否 |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` | 向后兼容保留，实际调用走 OfoxAI | 否 |

## API 概览

基础路径：`/api/v1`（共 50 个端点，分布在 13 个路由模块）。完整交互式文档见 `http://localhost:8000/docs`。

### 比赛 / 联赛
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/matches` | 比赛列表（多联赛 `league_ids` / 轮次 / 状态 / 日期 / 排序 / 限量筛选） |
| GET | `/matches/{match_id}` | 比赛详情（含各 AI 预测与综合摘要） |
| GET | `/matches/stats` | 首页 Hero 统计（比赛数/活跃 AI/预测数/用户数/联赛数） |
| GET | `/matches/home-tabs` | 首页 Tab 配置（近期/今日/明日/已结束） |
| GET | `/leagues` | 联赛列表（按 season 筛选） |
| GET | `/leagues/seasons/available` | 已有赛季列表 |
| GET | `/leagues/{league_id}` | 单个联赛详情 |

### 预测 / 排行榜 / 长期预测
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/predictions/match/{match_id}` | 某场比赛所有 AI 预测 |
| GET | `/predictions/compare/{match_id}` | 预测对比视图（含结果分布） |
| GET | `/leaderboard/ai` | AI 模型排行榜（按结果/比分命中率，支持多联赛） |
| GET | `/leaderboard/human` | 人机排行榜（含当前用户排名） |
| GET | `/leaderboard/ai/{model_id}` | 单个 AI 模型预测详情 |
| GET | `/long-term-predictions` | 冠亚季军长期预测 |

### 数据中心 / 球队 / 球员
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/standings` | 指定联赛积分榜（来自 `league_standings`，空则回退现算） |
| GET | `/standings/all` | 所有活跃联赛积分榜 |
| GET | `/data/player-rankings` | 球员榜（射手/助攻/黄牌/红牌，按联赛聚合） |
| GET | `/teams/{team_id}` | 球队详情（基础信息 + 赛季统计 + 近期状态） |
| GET | `/players/{player_id}` | 球员详情（主数据 + 各联赛赛季统计） |
| GET | `/cn-mappings` | 中英文映射（轮次/位置等，可按 category 过滤） |
| GET | `/proxy/avatar` | 图片代理（仅允许 sofifa 域名，绕过防盗链） |

### 用户
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/users/login` | 微信登录（code 换 openid，返回 JWT） |
| POST | `/users/vote` | 提交/修改预测投票（赛前可改） |
| GET | `/users/vote` | 查询用户对某场比赛的投票 |
| PUT | `/users/profile` | 更新用户资料（昵称/头像，微信临时 URL 自动转存） |
| GET | `/users/profile` | 用户资料 & 投票战绩统计 |
| GET | `/users/votes` | 用户投票历史（分页，支持多联赛） |
| POST | `/users/upload-avatar` | 上传头像文件（遗留直传入口） |
| GET | `/users/vip-status` | 获取用户 VIP 状态 |
| GET | `/users/search` | 通过昵称模糊搜索用户 |

### 管理后台 (`/admin`，内部/运维使用)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/cache/clear` | 清空所有缓存 |
| POST | `/admin/pipeline/sync` | 触发完整同步流水线 |
| POST | `/admin/matches/sync` | 同步比赛数据 |
| POST | `/admin/odds/sync` | 同步未来 7 天赔率（每日快照） |
| POST | `/admin/odds/sync-league` | 同步指定联赛全部比赛赔率（一次性全量，含历史） |
| POST | `/admin/stats/sync` | 同步积分榜 + 球队统计 + 近期状态 |
| POST | `/admin/h2h/sync` | 同步历史交锋 |
| POST | `/admin/player-stats/sync` | 重建球员盒子分（可选 `league_ids`） |
| POST | `/admin/standings/sync` | 同步官方积分榜（可选 `league_ids`） |
| POST | `/admin/players/season-stats/sync` | 重算球员赛季快照 |
| POST | `/admin/leagues/clone` | 克隆联赛到指定赛季（历史赛季回填） |
| POST | `/admin/leagues/backfill-season` | 一键回填历史赛季数据 |
| POST | `/admin/predictions/generate` | 批量生成 AI 预测 |
| POST | `/admin/predictions/generate/{match_id}` | 单场 AI 预测 |
| POST | `/admin/predictions/evaluate` | 评估已结束比赛预测准确性 |
| POST | `/admin/predictions/reevaluate` | 重新评估（含备选比分命中逻辑） |
| POST | `/admin/vip/add` | 添加 VIP 会员 |
| GET | `/admin/vip/list` | VIP 会员列表 |
| POST | `/admin/vip/renew` | 续费 VIP 会员 |
| DELETE | `/admin/vip/{member_id}` | 删除 VIP 会员 |
| GET | `/admin/vip/stats` | VIP 统计信息 |

## AI 模型阵容

模型阵容由数据库 `ai_models` 表驱动（字段：`name` / `model_id` / `avatar_url` / `style_tags` / `is_active`），可随时通过后台或 SQL 增删改、启停，**无硬编码上限**。当前默认接入约 10+ 个国内外主流模型，典型包括：

| 模型 | 产地 |
|------|------|
| DeepSeek | 🇨🇳 |
| 通义千问 Qwen | 🇨🇳 |
| 智谱 GLM | 🇨🇳 |
| Claude | 🇺🇸 |
| GPT | 🇺🇸 |
| Gemini | 🇺🇸 |
| 豆包 Doubao | 🇨🇳 |
| Kimi 月之暗面 | 🇨🇳 |
| MiniMax | 🇨🇳 |
| Grok | 🇺🇸 |
| 混元 Hunyuan | 🇨🇳 |
| 小车 MIMO | 🇨🇳 |

调用统一走 OfoxAI 网关（OpenAI 兼容 `AsyncOpenAI` 客户端），`prediction_graph.py` 用 LangGraph `StateGraph` 编排：`load_match → parallel_predict → validate_outputs → aggregate → validate_summary → END`（含失败重试）。

## 小程序页面结构

### 底部导航栏 (TabBar，4 个)
| Tab | 页面 | 说明 |
|-----|------|------|
| 首页 | `pages/index/index` | 比赛列表，按近期/今日/明日/已结束筛选，点击进入详情 |
| 排行 | `pages/leaderboard/index` | AI 排行 & 人类排行切换，支持轮次/联赛筛选 & 排序 |
| 数据 | `pages/data/index` | 数据中心：积分榜 / 球员榜（射手/助攻/牌），支持联赛切换 |
| 我的 | `pages/profile/index` | 个人中心，统计数据，VIP 状态，分享入口 |

### 子页面（共 15 个注册页面）
| 页面 | 路由 | 说明 |
|------|------|------|
| 比赛详情 | `pages/match-detail/index` | 完整 AI 预测分析，用户投票区，分享按钮 |
| 球队详情 | `pages/team-detail/index` | 球队基础信息 + 赛季统计 + 近期状态 |
| 球员详情 | `pages/player-detail/index` | 球员主数据 + 各联赛赛季统计 |
| 我的战绩 | `pages/vote-history/index` | 投票历史，命中率统计（仅已结束场次参与计算） |
| 首次设置 | `pages/profile-setup/index` | 昵称 & 头像填写 |
| AI 详情 | `pages/ai-detail/index` | 单个 AI 模型的详细战绩 |
| 关于 | `pages/about/index` | 开源信息，GitHub 地址，打赏收款码 |
| 免责声明 | `pages/disclaimer/index` | 免责声明 |
| 联系我们 | `pages/contact/index` | 联系方式 |
| 网页容器 | `pages/webview/index` | 外部网页承载 |
| 管理后台 | `pages/admin/index` | 运维管理入口 |

> 注：`pages/share-card/` 与 `pages/face-slap/` 目录仍存在，但已从 `app.config.ts` 注册页面中移除（分享卡片改由服务端生成，打脸合集功能已整合或下线）。

## 数据库表（18 张）

| 表名 | 说明 |
|------|------|
| `leagues` | 联赛（多联赛驱动；含 highlightly_league_id / season / type[league/cup]） |
| `teams` | 球队（含中文名、FIFA 排名、赛季统计、近期状态 JSON） |
| `matches` | 比赛赛程与结果（含 `league_id` 外键） |
| `ai_models` | AI 模型配置（阵容由 DB 驱动） |
| `predictions` | AI 单场预测（含比分/信心/分析/命中标记） |
| `prediction_summaries` | 多模型综合共识摘要 |
| `long_term_predictions` | 冠亚季军长期预测 |
| `users` | 微信用户 |
| `user_votes` | 用户投票记录（胜负 + 精确比分） |
| `head_to_heads` | 历史交锋数据 |
| `vip_members` | VIP 会员（user_id / plan_type / 起止时间） |
| `cn_mappings` | 中英文映射（轮次/位置等通用对照） |
| `match_player_stats` | 球员逐场盒子分（进球/助攻/牌/射门，球员榜数据源） |
| `league_standings` | 联赛官方积分榜（来自 Highlightly /standings 落地） |
| `players` | 球员主数据（含 sofifa 头像、位置、国籍、俱乐部等） |
| `player_season_stats` | 球员赛季统计快照（由 match_player_stats 聚合） |
| `bookmakers` | 博彩公司（highlightly_bookmaker_id 唯一） |
| `match_odds` | 比赛赔率快照（追加式，按 match/bookmaker/市场/日期唯一约束） |

> 迁移历史见 `server/alembic/versions/`（17 个版本，从初始表结构到多联赛、赔率、VIP、数据中心等）。

## 定时任务（APScheduler，6 个 cron job）

| Job ID | 周期 | 说明 |
|--------|------|------|
| `sync_matches_and_respond` | 每 30 分钟 | 同步比赛 + 事件驱动下游（新比赛→H2H，结束→统计+评估） |
| `generate_predictions` | 每日 01:00 | 生成 AI 预测 |
| `sync_standings_and_stats` | 每日 02:00 | 全量同步积分榜 + 球队统计 + 近期战绩 |
| `refresh_all_caches` | 每 5 分钟 | 刷新只读缓存（减少 DB 查询） |
| `sync_odds` | 每日 04:00 | 同步赛前赔率（prematch，未来 7 天） |
| `telegram_daily_push` | 每日 22:00 | Telegram 推送比赛预测和赛果 |

## Telegram 推送

支持通过 Telegram Bot 每日推送比赛信息和 AI 预测。

**功能特点：**
- 📅 每日 22:00 自动推送今日比赛预测
- 📋 昨日已结束比赛赛果
- 📊 AI 模型排行榜（每周一额外推送）
- 🔔 支持个人聊天和群组推送
- 🎯 支持多目标同时推送

**快速配置：**

1. 创建 Telegram Bot：[@BotFather](https://t.me/BotFather)
2. 获取 Chat ID：[@userinfobot](https://t.me/userinfobot)
3. 配置环境变量：

```bash
# server/.env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_IDS=your_chat_id_1,your_chat_id_2
```

**管理接口：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/telegram/test` | GET | 测试 Bot 连接 |
| `/admin/telegram/status` | GET | 查看配置状态 |
| `/admin/telegram/push` | POST | 手动触发每日推送 |
| `/admin/telegram/send` | POST | 发送自定义消息 |

详细配置说明见 [Telegram 配置指南](docs/TELEGRAM_SETUP.md)。

## 文档

- [产品需求文档](docs/REQUIREMENTS.md)
- [技术方案文档](docs/TECHNICAL_DESIGN.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [部署指南](docs/DEPLOYMENT.md)
- [Highlightly 集成](docs/HIGHLIGHTLY_INTEGRATION.md)
- [LangGraph 预测设计](docs/LANGGRAPH_PREDICTION_DESIGN.md)
- [多联赛方案](docs/MULTI_LEAGUE_PLAN.md)
- [赔率集成方案](docs/ODDS_INTEGRATION_PLAN.md)
- [Telegram 配置指南](docs/TELEGRAM_SETUP.md)
- [UI 设计稿](docs/ui-design.html)
- 各阶段汇报 (Phase 1 ~ Phase 4)
- 分享卡片相关 (SHARE_CARD_*.md)

## License

MIT
