# 世界杯 AI 预测大赛 — 技术方案文档

> 本文档描述系统**当前**的实际架构与设计。相比早期版本，主要变化：
> 1. 比赛数据源由 API-Football 切换为 **Highlightly**；
> 2. 由「单世界杯」升级为 **多联赛**（leagues 表驱动）；
> 3. 新增 **赔率**（bookmakers / match_odds）、**VIP 会员**、**数据中心**（积分榜/球员榜）等模块；
> 4. AI 预测改用 **LangGraph** 编排 + OfoxAI 统一网关。

## 1. 整体架构

```
┌─────────────────────────────────────────────────┐
│                  微信小程序 (Taro + React)         │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐             │
│  │ 首页 │ │ 排行 │ │ 数据 │ │ 我的 │  (4 Tab)     │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘             │
└─────┼────────┼────────┼────────┼─────────────────┘
      │        │        │        │
      ▼        ▼        ▼        ▼
┌─────────────────────────────────────────────────┐
│              服务器 (Docker / 裸机)                │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │       FastAPI (Python 3.12 + Uvicorn)        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │  │
│  │  │ REST API │ │ 定时任务  │ │ AI 调用网关  │ │  │
│  │  │ (50端点) │ │ (5 cron) │ │ (LangGraph)  │ │  │
│  │  └──────────┘ └──────────┘ └──────────────┘ │  │
│  │  ┌──────────┐ ┌──────────────────────────┐  │  │
│  │  │ 本地缓存  │ │ cachetools TTLCache       │  │  │
│  │  └──────────┘ └──────────────────────────┘  │  │
│  └────┬────────────────────────────────────────┘  │
│       ▼                                           │
│  ┌─────────┐                                      │
│  │ MySQL   │                                      │
│  │ (18表)  │                                      │
│  └─────────┘                                      │
└─────────────────────────────────────────────────┘
       │                               │
       ▼                               ▼
┌────────────┐                 ┌──────────────┐
│ Highlightly│                 │   OfoxAI     │
│ (比赛/积分/ │                 │ (AI 统一网关) │
│  球员/赔率) │                 │              │
└────────────┘                 └──────────────┘
```

**数据流向**：
- **比赛 / 积分榜 / 球员 / 赔率**：全部来自 Highlightly（`soccer.highlightly.net`），经各 `*_sync` service 落地到 MySQL。
- **AI 预测**：LangGraph 编排，逐模型调用 OfoxAI 网关（`api.ofox.io/v1`），结果写入 `predictions` / `prediction_summaries`。
- **客户端**：小程序通过 `/api/v1` 读取上述数据，缓存层（TTLCache）拦截高频只读查询。

## 2. 技术栈选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **小程序前端** | Taro 4 + React 18 + TypeScript | 跨端能力，后续可扩展 Web 版 |
| **UI 方案** | 自研 SCSS 组件（非组件库） | 轻量可控，避免包体积膨胀 |
| **状态管理** | Zustand | 轻量，适合小程序场景 |
| **后端框架** | FastAPI (Python 3.12) | 异步高性能，自动生成 API 文档 |
| **ASGI 服务器** | Uvicorn | 高性能异步服务器 |
| **ORM** | SQLAlchemy 2.0 + Alembic | 异步驱动（asyncmy）+ 迁移 |
| **数据库** | MySQL 8.0 | 成熟稳定 |
| **缓存** | cachetools (本地内存缓存) | 数据量小，无需 Redis |
| **定时任务** | APScheduler | 轻量级 Python 定时任务 |
| **HTTP 客户端** | httpx | 异步 HTTP，调用外部 API |
| **AI 编排** | LangGraph `StateGraph` | 多模型并行预测 + 聚合 + 重试 |
| **AI 网关** | OfoxAI (OpenAI 兼容 `AsyncOpenAI`) | 一个 Key、国内直连、覆盖国内外主流模型 |
| **比赛数据** | Highlightly | 替代 API-Football，覆盖比赛/积分榜/球员/赔率 |
| **反向代理** | Nginx | SSL、静态资源 |
| **部署** | Docker + Docker Compose | 一键部署，环境一致 |

## 3. 数据量分析与缓存方案

### 3.1 数据量评估

| 数据类型 | 预估总量 | 内存占用 | 说明 |
|----------|---------|---------|------|
| 比赛 | 数百~数千条（多联赛） | < 5MB | 列表分页读取 |
| AI 预测 | 比赛数 × 模型数 | 数十 MB | 按比赛缓存 |
| 排行榜 | 数十~数百条 | < 1MB | 聚合计算 |
| 用户投票 | 万级 | 查询时计算 | SQL 聚合 |
| 赔率快照 | 视比赛数 × 博彩公司 | 数十 MB | 仅详情页按需 |

**结论**：全量缓存到 Python 进程内存仍可控（< 100MB），用 `cachetools` 的 TTLCache 即可，无需 Redis。

### 3.2 缓存实现

`app/core/cache.py` 定义多组 TTLCache 实例，按业务划分 TTL：
- 只读类：`stats_cache`(5min)、`matches_cache`(5min)、`match_detail_cache`(10min)、`prediction_cache`(10min)、`compare_cache`(10min)、`leaderboard_cache`(5min)、`standings_cache`(10min)、`player_rankings_cache`(5min)、`long_term_cache`(30min)。
- 用户类：`user_profile_cache`、`user_votes_cache`、`user_vote_cache`（写后失效 `invalidate_user`）。

`cache_warmer.py` 的 `refresh_all_caches`（每 5 分钟）主动预热只读缓存，降低 DB 压力。

## 4. 数据库设计（18 张表）

> 完整 SQLAlchemy 模型见 `server/app/models/`，迁移见 `server/alembic/versions/`。

### 4.1 核心表清单

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `leagues` | name, cn_name, highlightly_league_id, season, type(league/cup), country, is_active, sort_order | 多联赛驱动核心 |
| `teams` | name, cn_name, flag_url, group_name, fifa_rank, season_stats(JSON), recent_form(JSON), highlightly_team_id | 球队 |
| `matches` | match_day, round, home_team_id, away_team_id, league_id(FK), match_time, venue, status, home_score, away_score, result, highlightly_match_id | 比赛 |
| `ai_models` | name, model_id(唯一), avatar_url, style_tags(JSON), is_active | 模型阵容（DB 驱动） |
| `predictions` | match_id, model_id, result, score_home/away, score_alt_*, confidence, analysis, is_correct_result, is_correct_score | 单场预测 |
| `prediction_summaries` | match_id, score_*, summary, short_summary, confidence | 多模型共识 |
| `long_term_predictions` | model_id, champion/runner_up/third_team_id, analysis | 冠亚季军 |
| `users` | openid(唯一), nickname, avatar_url | 微信用户 |
| `user_votes` | user_id, match_id, result, score_home/away, is_correct_* | 投票 |
| `head_to_heads` | home_team_id, away_team_id, detail(JSON) | 历史交锋 |
| `vip_members` | user_id, openid, plan_type(monthly/quarterly/yearly/permanent), start_at, expire_at | VIP |
| `cn_mappings` | category, key, cn_value, is_series | 中英文映射 |
| `match_player_stats` | match_id, player_id, team_id, league_id, goals, assists, cards, minutes… | 球员逐场盒子分 |
| `league_standings` | league_id, team_id, group_name, position, played, won, draw, lost, points… | 积分榜 |
| `players` | id(highlightly), name, cn_name, logo, position_*, height, citizenship, club… | 球员主数据 |
| `player_season_stats` | player_id, league_id, season, team_*, goals, assists, cards… | 球员赛季快照 |
| `bookmakers` | highlightly_bookmaker_id(唯一), name, is_active | 博彩公司 |
| `match_odds` | match_id, bookmaker_id, bookmaker_name, odds_type(prematch/live), market, value, odd, snapshot_date, fetched_at | 赔率快照 |

### 4.2 关键约束

- `match_odds` 唯一约束 `uk_match_odds`（match_id, bookmaker_id, odds_type, market, value, snapshot_date），**追加式每日快照**，用于构建赔率走势。
- `bookmakers.bookmaker_id` 指向 `bookmakers.highlightly_bookmaker_id`（历史迁移曾误指 `id`，后由 `q2r3s4t5u6v7` 修正）。
- `matches.league_id` / `teams` / `long_term_predictions` 等均有 `league_id` 外键，支撑多联赛隔离与聚合。

## 5. 后端 API 设计

基础路径 `/api/v1`，共 **50 个端点 / 13 个路由模块**。详见 README「API 概览」。模块划分：

| 模块 | 前缀 | 端点数 | 主要职责 |
|------|------|--------|----------|
| matches | `/matches` | 4 | 比赛列表/详情/首页统计/Tab |
| leagues | `/leagues` | 3 | 联赛列表/赛季/详情 |
| predictions | `/predictions` | 2 | 单场预测 / 对比 |
| leaderboard | `/leaderboard` | 3 | AI / 人类 / 单模型 |
| standings | `/standings` | 2 | 单联赛 / 全部积分榜 |
| users | `/users` | 9 | 登录/投票/资料/战绩/VIP状态/搜索 |
| admin | `/admin` | 21 | 同步/预测/VIP/历史赛季回填（运维） |
| long_term | `/long-term-predictions` | 1 | 长期预测 |
| cn_mapping | `/cn-mappings` | 1 | 中英文映射 |
| data | `/data` | 1 | 球员榜 |
| teams | `/teams` | 1 | 球队详情 |
| players | `/players` | 1 | 球员详情 |
| proxy | `/proxy` | 1 | sofifa 图片代理 |

> 注：`fun_fact.py` / `share.py` / `round_translations.py` 已为空文件（历史遗留，未注册路由）。

## 6. 核心业务流程

### 6.1 数据同步编排（`sync_pipeline.py`）

```
每 30 分钟 (APScheduler sync_matches_and_respond)
  │
  ├── 1. 遍历所有活跃联赛 (match_sync.get_active_leagues)
  │       └── 调用 Highlightly 拉取比赛 → 更新 matches 表
  │
  ├── 2. 事件驱动下游：
  │       ├── 新增比赛 → 触发 H2H 同步 (h2h_sync)
  │       └── 比赛结束 → 触发 stats_sync + prediction_evaluator
  │
  └── 3. 写后失效相关缓存
```

其他同步 job（每日 02:00 `sync_standings_and_stats`、每日 04:00 `sync_odds`）独立运行，补全积分榜/球员/赔率数据。

### 6.2 AI 预测生成流程（LangGraph）

```
每日 01:00 (APScheduler generate_predictions) 或手动触发
  │
  └── prediction_graph.StateGraph:
        load_match
          └── 读取比赛 + 两队信息 + 历史交锋 + 球队统计
        parallel_predict (并行)
          └── 对每个 is_active 的 AI 模型：
                ├── 构建 Prompt（prompt_builder）
                ├── 调用 OfoxAI（AsyncOpenAI，兼容 OpenAI 格式）
                ├── prediction_parsers 解析 JSON（多模型适配 + 修复）
                └── 存入 predictions 表
        validate_outputs → retry_failed（失败重试）
        aggregate
          └── 用汇总模型（默认 DeepSeek）综合所有预测 → prediction_summaries
        validate_summary → END
```

### 6.3 预测评估流程

```
比赛结束后（事件驱动 / 手动 /admin/predictions/evaluate）
  │
  ├── 1. 更新 matches（status=finished, 比分, result）
  ├── 2. 批量评估 predictions：
  │       ├── is_correct_result = (预测胜负 == 实际胜负)
  │       └── is_correct_score = (预测比分 == 实际比分，含备选比分)
  └── 3. 刷新排行榜 / 用户战绩缓存
```

### 6.4 赔率同步（`odds_service.py`）

- `sync_all_upcoming_odds`：每日 04:00，仅同步未来 7 天 `upcoming` 比赛，追加式快照。
- `sync_league_odds(league_id)`：一次性拉全量（含历史赛事），用于补齐如已结束世界杯的完整赔率。
- 有效博彩公司白名单 `ACTIVE_BOOKMAKER_IDS`，市场白名单 `MARKET_WHITELIST`（胜平负 / 进球数等）。

## 7. 项目结构

### 7.1 整体目录

```
world-cup-prediction/
├── client/                          # Taro 小程序
├── server/                          # FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # 入口 + 生命周期
│   │   ├── config.py                # Pydantic Settings
│   │   ├── database.py              # SQLAlchemy 异步引擎
│   │   ├── deps.py                  # 依赖注入
│   │   ├── models/                  # 18 张表 ORM（19 个类）
│   │   ├── schemas/                 # 14 个 Pydantic 模型
│   │   ├── api/
│   │   │   ├── router.py            # 路由聚合 (/api/v1)
│   │   │   └── v1/                  # 13 个有效路由模块
│   │   ├── services/                # 16 个业务逻辑模块
│   │   ├── core/                    # ofoxai / highlightly / wechat / scheduler / cache / auth
│   │   └── utils/prompt_builder.py  # Prompt 模板
│   ├── alembic/versions/            # 17 个迁移
│   ├── static/                      # 头像 / 代理缓存
│   └── docker-compose.yml / Dockerfile
├── docs/                            # 文档
└── (scripts/ 如需部署脚本)
```

### 7.2 后端模块要点

- **models/**：`league, team, match, ai_model, prediction, prediction_summary, long_term_prediction, user, user_vote, head_to_head, vip_member, cn_mapping, match_player_stat, data_detail(LeagueStanding/Player/PlayerSeasonStat), odds(Bookmaker/MatchOdd/OddsType)`。
- **services/**：同步类（`match_sync, stats_sync, player_stats_sync, standings_sync, h2h_sync, odds_service`）、预测类（`ai_predictor, prediction_graph, prediction_parsers, prediction_evaluator`）、计算类（`leaderboard_calc, standings_calc`）、业务类（`vip_service, sync_pipeline`）。
- **core/**：`ofoxai`（OfoxAI 网关，含 `_MODEL_TEMPERATURE_OVERRIDES` 与 `_extract_json` 多策略修复）、`highlightly`（Highlightly 客户端）、`scheduler`（5 job）、`cache` / `cache_warmer`、`wechat`、`auth`。

## 8. Docker 部署方案

详见 [部署指南](DEPLOYMENT.md)。要点：

- `docker-compose.yml` 编排 `db`(mysql:8.0) / `api`(FastAPI) / `nginx`。
- `entrypoint.sh` 启动顺序：等待 MySQL → `alembic upgrade head` → 启动 uvicorn。
- 数据库名 `worldcup_prediction`，`DATABASE_URL` 由 `DB_*` 环境变量拼接（asyncmy 异步 / pymysql 同步迁移）。
- 生产 HTTPS 由 Nginx 终止，反向代理 `/api/` 到 `api:8000`。

## 9. 服务器资源规划（2核2G）

| 组件 | 内存占用 | 说明 |
|------|---------|------|
| MySQL 8.0 | ~350MB | buffer_pool + 连接池 |
| FastAPI (2 workers) | ~150MB | uvicorn + Python |
| Nginx | ~20MB | - |
| 系统 + 余量 | ~480MB | 充足 |
| **合计** | **~1GB** | 比使用 Redis 方案省约 200MB |

> 若后续用户量增长，优先扩容到 2核4G。

## 10. Python 核心依赖

```
# Web 框架
fastapi==0.115.0
uvicorn[standard]==0.30.0

# 数据库
sqlalchemy[asyncio]==2.0.35
asyncmy==0.2.9
alembic==1.13.0

# 缓存
cachetools==5.5.0

# HTTP 客户端
httpx==0.27.0

# 定时任务
apscheduler==3.10.4

# AI 编排
langgraph (LangGraph StateGraph)

# 数据验证
pydantic==2.9.0
pydantic-settings==2.5.0

# 微信小程序
wechatpy==2.1.0

# 图片生成(分享卡片/头像)
Pillow==10.4.0

# 工具
python-dotenv==1.0.1
loguru==0.7.2
```

## 11. AI 模型网关 — OfoxAI

### 11.1 为什么选择 OfoxAI

| 对比项 | OfoxAI | 多网关方案 |
|--------|--------|-----------|
| API Key 数量 | 1 个 | 多个 |
| 网络要求 | 国内直连 | 部分需代理 |
| 模型覆盖 | 国内外 100+ 模型 | 各自覆盖一部分 |
| API 格式 | 兼容 OpenAI | 各自兼容 OpenAI |
| 维护复杂度 | 低（单网关） | 高（多网关+降级） |

**OfoxAI 优势**：一个 Key、一个 base_url、国内直连，覆盖 GPT/Claude/Gemini/DeepSeek/Qwen/GLM 等全部主流模型。

> 网关地址：**`https://api.ofox.io/v1`**（注意是 `ofox.io`，非 `ofox.ai`）。客户端使用 OpenAI 兼容的 `AsyncOpenAI`。

### 11.2 模型阵容（DB 驱动）

模型阵容由 `ai_models` 表驱动（可随时增删改、启停），无硬编码上限。当前默认接入约 10+ 个国内外主流模型，典型供应商：

| 供应商 | 产地 | 备注 |
|--------|------|------|
| DeepSeek | 🇨🇳 | 汇总模型默认（DeepSeek） |
| 通义千问 Qwen | 🇨🇳 | 含推理模型（注意 reasoning_tokens 占用） |
| 智谱 GLM | 🇨🇳 | - |
| Claude | 🇺🇸 | - |
| GPT | 🇺🇸 | - |
| Gemini | 🇺🇸 | 输出易截断，parsers 有专门处理 |
| 豆包 Doubao | 🇨🇳 | - |
| Kimi 月之暗面 | 🇨🇳 | `moonshotai/kimi-k3` 强制 temperature=1 |
| MiniMax | 🇨🇳 | 响应回传可能卡死，需超时重试 |
| Grok | 🇺🇸 | - |
| 混元 Hunyuan | 🇨🇳 | - |
| 小车 MIMO | 🇨🇳 | - |

### 11.3 OfoxAI 客户端实现（`app/core/ofoxai.py`）

```python
# 使用 OpenAI 兼容的 AsyncOpenAI 客户端
from openai import AsyncOpenAI

class OfoxAIClient:
    BASE_URL = "https://api.ofox.io/v1"

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=self.BASE_URL, timeout=...)

    async def chat_completion(self, model, messages, temperature, max_tokens):
        resp = await self.client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        return resp.choices[0].message.content
```

- `_MODEL_TEMPERATURE_OVERRIDES`：如 `moonshotai/kimi-k3` 固定 `temperature=1.0`。
- `_extract_json`：多策略修复 LLM 返回的 JSON（去 markdown 包裹、补括号、截断修复等）。
- 推理模型（如 Qwen3.6）会优先消耗 `reasoning_tokens`，需调大 `max_tokens` 避免输出为空。

## 12. 外部数据源接入

### 12.1 Highlightly（比赛 / 积分榜 / 球员 / 赔率）

- 地址：`https://soccer.highlightly.net`（RapidAPI 代理路径需带 `/football` 前缀）。
- 覆盖：比赛赛程与比分、积分榜（`/standings`）、球员盒子分、历史交锋、博彩公司赔率。
- 各 `*_sync` service 负责拉取并落地；`leagues` 表以 `highlightly_league_id` 关联 Highlightly 联赛 ID。
- 注意：Highlightly 对历史赛事（>28 天）的赔率可能拉取不到，需用 `sync_league_odds` 一次性补齐或接受缺数。

### 12.2 OfoxAI（AI 模型）

- 地址：`https://api.ofox.io/v1`。
- 费用按 token 计费，不同模型差异大；单次预测约 500 input + 200 output tokens。
- 国内可直连，无需代理。

## 13. 里程碑

- 2026 世界杯于 **6 月 11 日**开赛。
- 当前系统已超越单一世界杯，演进为多联赛足球数据 + AI 预测平台，新增赔率、VIP、数据中心等模块。

| 阶段 | 目标 | 状态 |
|------|------|------|
| P0 基础搭建 | 脚手架 / 数据库 / Docker / Key | 已完成 |
| P1 核心功能 | 比赛同步 / AI 预测 / 展示 / 排行榜 | 已完成 |
| P2 用户功能 | 微信登录 / 投票 / 人机排行 | 已完成 |
| P3 增强功能 | 多联赛 / 赔率 / VIP / 数据中心 | 已完成 |
| P4 上线 | 审核 / 部署 / 运维 | 进行中 |
