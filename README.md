# 🏆 AI 预测世界杯

让多个 AI 大模型同台竞技，预测 2026 FIFA 世界杯比赛结果。用户可以围观 AI 预测、参与投票、与 AI 一较高下，并通过社交分享扩大传播。

**开源地址**: [https://github.com/AndyXu-Citi/world-cup-prediction](https://github.com/AndyXu-Citi/world-cup-prediction)

## 产品亮点

- **AI 对决**：10 个主流 AI 模型同台预测，看谁更准
- **人机大战**：用户投票预测（胜负 + 精确比分），与 AI 模型一较高下
- **排行榜**：AI 排行榜 / 人类排行榜双维度，胜负命中率 & 比分命中率独立统计
- **数据中心**：积分榜 + 球队数据榜 + 球员榜（射手/助攻/牌），按联赛切换视角
- **分享传播**：支持分享给好友和分享到朋友圈
- **AI 综合分析**：多模型预测聚合为共识结论 + 信心指数
- **趣闻生成**：基于用户战绩动态调用 DeepSeek 生成足球小知识

## 技术架构

```
微信小程序 (Taro + React + SCSS)
         │
         ▼
    FastAPI (Python)
    ├── REST API (23+ 个端点)
    ├── APScheduler 定时任务
    ├── LangGraph + OfoxAI 统一网关 (11 个 AI 模型)
    ├── Highlightly 比赛数据源
    └── Pillow 分享卡片图片生成
         │
         ▼
    MySQL 8.0
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 小程序前端 | Taro 4.1 + React 18 + TypeScript + Zustand + SCSS |
| 后端框架 | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| 数据库 | MySQL 8.0 (asyncmy) |
| 缓存 | cachetools TTLCache |
| 定时任务 | APScheduler |
| HTTP 客户端 | httpx (async) |
| AI 网关 | OfoxAI + LangGraph 编排 |
| 比赛数据 | Highlightly |
| 图片处理 | Pillow |
| 认证 | JWT + 微信静默登录 |
| 部署 | Docker Compose + Nginx |

## 项目结构

```
world-cup-prediction/
├── client/                          # Taro 小程序前端
│   ├── src/
│   │   ├── app.config.ts            # 页面路由 & TabBar 配置 (10 页面)
│   │   ├── app.ts                   # 应用入口 (微信静默登录)
│   │   ├── assets/                  # 静态资源 (图标/SVG/收款码)
│   │   ├── pages/                   # 页面目录
│   │   │   ├── index/               # 首页 - 比赛列表 + Tab 筛选
│   │   │   ├── match-detail/        # 比赛详情 - AI 预测 + 用户投票
│   │   │   ├── leaderboard/         # 排行榜 - AI / 人类双 Tab
│   │   │   ├── data/                # 数据中心 - 积分榜 / 球队榜 / 球员榜
│   │   │   ├── profile/             # 个人中心 - 统计 & 趣闻
│   │   │   ├── profile-setup/       # 首次设置 - 昵称 & 头像
│   │   │   ├── share-card/          # 分享卡片展示
│   │   │   ├── vote-history/        # 我的战绩 - 投票历史
│   │   │   ├── ai-detail/           # AI 模型详情
│   │   │   └── about/               # 关于小程序
│   │   ├── services/api.ts          # 后端 API 封装
│   │   ├── stores/index.ts          # Zustand 状态管理 (3 Store)
│   │   └── styles/                  # 全局样式 & 变量
│   └── config/                      # Taro 构建配置
│
├── server/                          # FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # 入口 + 生命周期
│   │   ├── config.py                # Pydantic Settings 配置
│   │   ├── database.py              # SQLAlchemy 异步引擎
│   │   ├── models/                  # ORM 模型 (11 张表)
│   │   ├── schemas/                 # Pydantic 模型 (8 个)
│   │   ├── api/v1/                  # 路由模块 (9 个文件)
│   │   │   ├── matches.py           # 比赛接口
│   │   │   ├── predictions.py       # AI 预测接口
│   │   │   ├── leaderboard.py       # 排行榜接口
│   │   │   ├── users.py             # 用户 & 投票接口
│   │   │   ├── share.py             # 分享卡片接口
│   │   │   ├── admin.py             # 管理员接口
│   │   │   ├── long_term.py         # 冠亚季军预测接口
│   │   │   ├── fun_fact.py          # 趣闻生成接口
│   │   │   └── data.py              # 数据中心接口 (积分榜/球队榜/球员榜)
│   │   ├── services/                # 业务逻辑 (13 个)
│   │   │   ├── sync_pipeline.py     # 数据同步编排
│   │   │   ├── match_sync.py        # 比赛数据同步 (Highlightly)
│   │   │   ├── stats_sync.py        # 球队统计同步 (遍历所有活跃联赛)
│   │   │   ├── player_stats_sync.py # 球员盒子分同步 (按场聚合球员榜)
│   │   │   ├── h2h_sync.py          # 历史交锋同步
│   │   │   ├── ai_predictor.py      # AI 预测服务
│   │   │   ├── prediction_graph.py  # LangGraph 预测编排图
│   │   │   ├── prediction_parsers.py# LLM 输出解析
│   │   │   ├── prediction_evaluator.py # 预测准确性评估
│   │   │   ├── leaderboard_calc.py  # 排行榜计算
│   │   │   ├── seed.py              # 种子数据
│   │   │   └── share_card.py        # 分享卡片图片生成
│   │   ├── core/                    # 核心模块
│   │   │   ├── ofoxai.py            # OfoxAI 网关
│   │   │   ├── highlightly.py       # Highlightly 数据客户端
│   │   │   ├── wechat.py            # 微信登录
│   │   │   ├── scheduler.py         # 定时任务调度
│   │   │   ├── cache.py             # 缓存封装
│   │   │   └── auth.py              # JWT 认证
│   │   └── utils/prompt_builder.py  # LLM Prompt 模板
│   ├── alembic/                     # 数据库迁移 (7 版本)
│   ├── start.sh / stop.sh / restart.sh  # 服务管理脚本
│   ├── docker-compose.yml           # Docker 编排
│   ├── Dockerfile
│   └── requirements.txt
│
└── docs/                            # 项目文档
```

## 快速开始

### 环境要求

- Python 3.9+
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

## 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `DB_PASSWORD` | MySQL 密码 | 是 |
| `DB_HOST` | 数据库地址 (本地 127.0.0.1，Docker 用 db) | 否 (默认 localhost) |
| `OFOXAI_API_KEY` | OfoxAI 统一网关密钥 | 是 |
| `OFOXAI_BASE_URL` | OfoxAI 网关地址 | 否 (默认值) |
| `HIGHLIGHTLY_API_KEY` | Highlightly 比赛数据 API Key | 是 |
| `WECHAT_APP_ID` | 微信小程序 AppID | 是 |
| `WECHAT_APP_SECRET` | 微信小程序 AppSecret | 是 |
| `SECRET_KEY` | JWT 签名密钥 (生产环境必须修改) | 否 (有默认值) |

## API 概览

基础路径：`/api/v1`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/matches` | 比赛列表 (支持筛选/分页) |
| GET | `/matches/{id}` | 比赛详情 |
| GET | `/matches/{id}/predictions` | 比赛 AI 预测列表 |
| POST | `/users/login` | 微信登录 |
| POST | `/users/vote` | 提交/修改预测投票 |
| PUT | `/users/profile` | 更新用户资料 (昵称/头像) |
| GET | `/users/profile` | 用户资料 & 投票统计 |
| GET | `/users/votes` | 用户投票历史列表 |
| GET | `/users/avatar/upload` | 上传头像 |
| GET | `/leaderboard/ai` | AI 模型排行榜 |
| GET | `/leaderboard/human` | 人类排行榜 |
| GET | `/standings` | 积分榜 (按联赛/杯赛分组) |
| GET | `/data/player-rankings` | 球员榜 (射手/助攻/黄牌/红牌，按联赛聚合) |
| GET | `/long-term-predictions` | 冠亚季军长期预测 |
| GET | `/share/card/{matchId}` | 分享卡片数据 (JSON) |
| GET | `/share/card/{matchId}/image` | 分享卡片图片 (PNG) |
| GET | `/fun-fact` | 动态趣闻 (DeepSeek 生成) |
| POST | `/admin/matches/sync` | 同步比赛数据 |
| POST | `/admin/stats/sync` | 同步球队统计（遍历所有活跃联赛的积分榜 + 近期状态） |
| POST | `/admin/player-stats/sync` | 全量回填球员盒子分（重建所有活跃联赛的球员榜） |
| POST | `/admin/predictions/generate` | 批量生成 AI 预测 |
| POST | `/admin/predictions/generate/{matchId}` | 单场 AI 预测 |
| POST | `/admin/predictions/evaluate` | 评估已结束比赛的预测准确性 |

完整文档: `http://localhost:8000/docs`

## AI 模型阵容

通过 OfoxAI 统一网关 + LangGraph 编排调用：

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

## 小程序页面结构

### 底部导航栏 (TabBar)

| Tab | 页面 | 说明 |
|-----|------|------|
| 首页 | `pages/index/index` | 比赛列表，按小组赛/淘汰赛/今日/明日/已结束筛选，点击卡片进入详情 |
| 排行 | `pages/leaderboard/index` | AI 排行 & 人类排行切换，支持轮次筛选 & 排序 |
| 数据 | `pages/data/index` | 数据中心：积分榜 / 球队榜 / 球员榜（射手/助攻/牌），支持联赛切换 |
| 我的 | `pages/profile/index` | 个人中心，统计数据，趣闻，分享入口 |

### 子页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 比赛详情 | `pages/match-detail/index` | 完整 AI 预测分析，用户投票区，分享按钮 |
| 我的战绩 | `pages/vote-history/index` | 投票历史，命中率统计 (仅已结束场次参与计算) |
| 首次设置 | `pages/profile-setup/index` | 昵称 & 头像填写 |
| 分享卡片 | `pages/share-card/index` | 精美预测卡片展示与保存 |
| AI 详情 | `pages/ai-detail/index` | 单个 AI 模型的详细战绩 |
| 关于 | `pages/about/index` | 开源信息，GitHub 地址，打赏收款码 |

## 数据库表

| 表名 | 说明 |
|------|------|
| `teams` | 球队信息 (含中文别名、FIFA 排名) |
| `matches` | 比赛赛程与结果 (104 场) |
| `ai_models` | AI 模型配置 (12 个模型) |
| `predictions` | AI 单场预测 (含比分/信心/分析) |
| `prediction_summaries` | 多模型综合共识摘要 |
| `long_term_predictions` | 冠亚季军长期预测 |
| `users` | 微信用户 |
| `user_votes` | 用户投票记录 (胜负+精确比分) |
| `head_to_heads` | 历史交锋数据 |
| `team_stats` | 球队近期统计数据 |
| `match_player_stats` | 球员逐场盒子分（进球/助攻/牌/射门，球员榜数据源） |

## 文档

- [产品需求文档](docs/REQUIREMENTS.md)
- [技术方案文档](docs/TECHNICAL_DESIGN.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [部署指南](docs/DEPLOYMENT.md)
- [Highlightly 集成](docs/HIGHLIGHTLY_INTEGRATION.md)
- [LangGraph 预测设计](docs/LANGGRAPH_PREDICTION_DESIGN.md)
- [UI 设计稿](docs/ui-design.html)
- 各阶段汇报 (Phase 1 ~ Phase 4)

## License

MIT
