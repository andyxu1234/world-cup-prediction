# Highlightly API 集成文档

## 概述

项目使用 [Highlightly Football API](https://soccer.highlightly.net) 替代 API-Football 作为数据源，获取 2026 世界杯赛程、比分、阵容、事件等数据。

**核心优势：** 免费 Basic 计划（100 次/天）即可访问完整世界杯数据，无需付费订阅。

---

## 架构

```
Highlightly API (https://soccer.highlightly.net)
     │
     ▼
HighlightlyClient (server/app/core/highlightly.py)
     │
     ▼
match_sync.py (server/app/services/match_sync.py)
     │
     ▼
MySQL (matches / teams 表)
```

---

## 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `HIGHLIGHTLY_API_KEY` | API 密钥 | - |
| `HIGHLIGHTLY_BASE_URL` | API 基础 URL | `https://soccer.highlightly.net` |
| `HIGHLIGHTLY_LEAGUE_ID` | 世界杯联赛 ID | `1635` |
| `HIGHLIGHTLY_SEASON` | 赛季年份 | `2026` |

认证方式：请求头 `x-rapidapi-key: <API_KEY>`

---

## HighlightlyClient 方法一览

### Matches（比赛）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_matches(date?, league_id?, season?, limit, offset)` | `GET /matches` | 获取比赛列表 | `{"data": [...], "pagination": {...}}` |
| `get_match_by_id(match_id)` | `GET /matches/{id}` | 单场详情（含 events/statistics/venue/predictions） | `dict` |
| `get_matches_by_date(date)` | `GET /matches?date=...` | 指定日期的世界杯比赛 | `list[dict]` |
| `get_all_world_cup_matches()` | `GET /matches`（自动翻页） | 全量获取世界杯所有比赛 | `list[dict]` |

### Standings（积分榜）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_standings(league_id?, season?)` | `GET /standings` | 小组积分榜 | `dict` |

### Highlights（集锦）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_highlights(league_id?, match_id?, date?, limit, offset)` | `GET /highlights` | 比赛集锦视频 | `dict` |

### Head to Head（交锋）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_head_to_head(team_id_one, team_id_two)` | `GET /head-2-head` | 两队历史交锋（最近10场） | `list[dict]` |

### Lineups（阵容）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_lineups(match_id)` | `GET /lineups/{matchId}` | 首发阵容 | `dict` |

### Events（事件）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_events(match_id)` | `GET /events/{matchId}` | 实时事件（进球/红黄牌/换人） | `list[dict]` |

### Statistics（统计）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_statistics(match_id)` | `GET /statistics/{matchId}` | 比赛统计数据 | `list[dict]` |

### Teams（球队）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_teams(name?, limit, offset)` | `GET /teams` | 球队列表 | `dict` |

### Countries（国家）

| 方法 | API 端点 | 说明 | 返回 |
|------|----------|------|------|
| `get_countries(name?)` | `GET /countries` | 国家列表 | `list[dict]` |

### Rate Limit（配额）

| 方法 | 说明 | 返回 |
|------|------|------|
| `get_rate_limit_info()` | 获取当前配额信息 | `{"limit": "100", "remaining": "91"}` |

配额信息从响应头 `x-ratelimit-requests-limit` / `x-ratelimit-requests-remaining` 读取。

---

## 数据同步逻辑（match_sync.py）

### 状态映射

| Highlightly `state.description` | MatchStatus |
|--------------------------------|-------------|
| Not started / Postponed / Cancelled / To be announced | `upcoming` |
| First half / Second half / Half time / Extra time / Penalties / Break time / In progress / Suspended / Interrupted | `live` |
| Finished / Finished after penalties / Finished after extra time / Awarded / Abandoned | `finished` |

### 比分解析

从 `state.score.current` 字段解析，格式为 `"3 - 1"`，拆分为主队/客队分数。

### 数据库字段映射

| Match 模型字段 | Highlightly 数据源 |
|---------------|---------------------|
| `highlightly_id` | `match.id` |
| `match_day` | 从 `match.date` 计算（6月11日=第1天） |
| `round` | `match.round` |
| `home_team_id` | 通过 `match.homeTeam.name` 匹配 Team 表 |
| `away_team_id` | 通过 `match.awayTeam.name` 匹配 Team 表 |
| `match_time` | `match.date` |
| `venue` | `get_match_by_id()` 详情中的 `venue.name` |
| `status` | 从 `match.state.description` 映射 |
| `home_score` | `match.state.score.current` 拆分 |
| `away_score` | `match.state.score.current` 拆分 |
| `result` | 根据 home_score/away_score 计算 |

### 同步任务

#### `sync_matches()` — 全量同步

- 每日 00:00 执行
- 调用 `get_all_world_cup_matches()` 拉取所有 72 场比赛
- 对每场比赛执行 `_upsert_match()`：不存在则创建，已存在则更新状态/比分
- 球队通过 name 匹配已有 Team 记录（来自 seed 数据）

#### `sync_live_scores()` — 增量比分同步

- 比赛日时段轮询（12:00-06:00，每 30 分钟）
- 仅拉取今天和明天的比赛（`get_matches_by_date`）
- 通过 `highlightly_id` 匹配数据库记录，只更新状态和比分
- 不创建新记录，不拉历史数据

---

## 定时任务调度（scheduler.py）

| 任务 | Cron 表达式 | 说明 | 日消耗 |
|------|-------------|------|--------|
| `sync_matches` | `0 0 * * *` | 每日 00:00 全量同步 | 1 次 |
| `sync_live_scores` | `*/30 0-6,12-23 * * *` | 12:00-06:00 每30分钟 | ~36 次 |
| `generate_predictions` | `0 1 * * *` | 每日 01:00 AI 预测 | 0 次（不调 API） |
| `evaluate_predictions` | `*/30 * * * *` | 每30分钟评估预测 | 0 次（不调 API） |

**日消耗总计：~37 次（100 次额度内，余量 63 次）**

---

## 配额控制策略（方案3：比赛日时段轮询）

核心思路：**只在有比赛的时段高频轮询，其余时间低频或跳过**。

- 每日 00:00 全量同步 1 次
- 比赛日当天 12:00 ~ 次日 06:00（覆盖美洲时区晚间比赛），每 30 分钟同步一次
- 非比赛时段（06:00-12:00）不轮询，节省配额
- 如需更高频率，可升级 Pro 计划（$9.49/月，7500 次/天）

---

## 依赖注入

```python
# server/app/deps.py
HighlightlyDep = Annotated[HighlightlyClient, Depends(get_highlightly_client)]
```

在路由中使用：

```python
@router.get("/matches")
async def list_matches(client: HighlightlyDep):
    matches = await client.get_all_world_cup_matches()
    return matches
```

---

## 迁移记录

- `api_football_id` → `highlightly_id`（Alembic 迁移 `a2b3c4d5e6f7`）
- `APIFootballClient` → `HighlightlyClient`
- `APIFootballDep` → `HighlightlyDep`

---

## 扩展功能（Phase 3 可选）

| 功能 | 方法 | 用途 |
|------|------|------|
| 比赛集锦 | `get_highlights()` | 前端展示视频集锦 |
| 首发阵容 | `get_lineups()` | 赛前展示双方阵容 |
| 历史交锋 | `get_head_to_head()` | AI 预测参考数据 |
| 小组积分榜 | `get_standings()` | 前端展示排名 |
| 实时事件 | `get_events()` | 比赛直播时间线 |
| 比赛统计 | `get_statistics()` | 控球率/射门等数据 |
