# Highlightly Football API 未接入端点盘点

> 对比对象：`highlightly.py` 客户端 + 实际调用站点（services / api / scripts）
> API 版本：Football API Documentation (8.2.5)
> 项目：world-cup-prediction（2026 世界杯预测，React/Taro 前端 + FastAPI 后端 + MySQL）
> 盘点日期：2026-07-22

## 一、总体结论

Highlightly 共 **25 个 GET 端点**。项目已实际打通（有调用站点）的 **10 个**：

| 端点 | 客户端方法 | 调用位置 |
|------|-----------|---------|
| `GET /leagues` | `get_leagues` | `scripts/sync_epl.py` |
| `GET /matches` | `get_matches` / `get_all_matches_by_league` | `services/match_sync.py`、`scripts/diagnose_match_times.py` |
| `GET /matches/{id}` | `get_match_by_id` | `scripts/diagnose_match_times.py` |
| `GET /teams/statistics/{id}` | `get_team_statistics` | `services/stats_sync.py` |
| `GET /standings` | `get_standings` | `services/stats_sync.py`、`services/standings_sync.py` |
| `GET /last-five-games` | `get_last_five_games` | `services/stats_sync.py` |
| `GET /head-2-head` | `get_head_to_head` | `services/h2h_sync.py` |
| `GET /box-score/{matchId}` | `get_box_score` | `services/player_stats_sync.py` |
| `GET /odds` | `get_odds` | `services/odds_service.py` |
| `GET /players/{id}` | `get_player_by_id` | `api/v1/players.py` |

**未使用端点 = 25 − 10 = 15 个**，分两层：

- **A 层（完全未接线，连客户端方法都没有）：6 个**
- **B 层（已写客户端方法但从未被任何 service/api 调用，休眠）：9 个**

---

## 二、A 层：连客户端方法都没有的端点（6 个）

需要先在 `highlightly.py` 补一个客户端方法，才能使用。

### 1. `GET /bookmakers` — 博彩公司列表
- **返回数据**：`{ data: [{ id, name }], pagination, plan }`，即 Highlightly 支持的博彩公司清单。
- **当前情况**：项目 `bookmakers` 表是靠 Alembic 种子 + 硬编码白名单 `ACTIVE_BOOKMAKER_IDS = {4,319,11,3,10,66,23,55,17,9}`（`odds_service.py`）填充的，`/odds` 返回的 `bookmakerId` 只是拿来做过滤，从未主动拉取过公司清单。
- **后续用法（高价值）**：
  - 用该接口**动态刷新/校验 `bookmakers` 表**，不再依赖硬编码 ID，避免供应商下架/新增博彩公司时数据失准。
  - 可作为 `/internal/odds` 私密赔率页的「博彩公司筛选器」数据源。

### 2. `GET /bookmakers/{id}` — 单个博彩公司
- **返回数据**：`[{ id, name }]`。
- **后续用法**：丰富单个博彩公司元数据的兜底接口；在 A 层 1 已拉全量清单的前提下，单独按 ID 查询价值较低，可作为补充。

### 3. `GET /countries/{countryCode}` — 按 ISO 码查国家
- **返回数据**：`[{ code, name, logo }]`。
- **后续用法**：
  - 世界杯全是**国家队**，可用 ISO 码反查国家 logo（国旗），用于前端球队/对阵展示。
  - 作为 `teams` 与 `countries` 的关联锚点（目前 `countries` 数据完全没接入）。

### 4. `GET /leagues/{id}` — 按 ID 查联赛
- **返回数据**：联赛对象（id, logo, name, country, seasons）。
- **后续用法**：
  - 世界杯在 Highlightly 里本身也是一个「league」。可用它**动态拉取世界杯联赛的元数据/赛季列表**，替代当前在 config 里写死的 `highlightly_league_id` / `season`。
  - 同步前做一次存在性校验，避免拿到脏 ID。

### 5. `GET /highlights/geo-restrictions/{id}` — 集锦地理限制
- **返回数据**：`{ state, allowedCountries, blockedCountries, embeddable }`。
- **限制**：**Basic/Free 计划不可用**（需付费）。
- **后续用法**：若在小程序里内嵌比赛集锦视频，需先判断 `embeddable` 与 `blockedCountries`（如中国大陆可能被 block），决定是内嵌 `<iframe>` 还是只给外链。

### 6. `GET /highlights/{id}` — 单个集锦
- **返回数据**：单个集锦对象（id, type, imgUrl, title, description, url, embedUrl, match, channel, source, category）。
- **后续用法**：用户从列表收藏/分享某条集锦后，用此接口按 ID 取最新元数据（标题/封面可能更新），配合 `/highlights` 列表使用。

---

## 三、B 层：已写客户端方法但从未调用的端点（9 个）

客户端封装已就绪，**只需在 service / api 里调用即可落地**，无需改 `highlightly.py`。

### 7. `GET /countries` → `get_countries()`
- **返回数据**：国家数组（code, name, logo），每日刷新。
- **后续用法**：一次性 seed 国家队参考表；给前端提供「国家筛选」；作为球队→国家 logo 的映射源（世界杯场景很实用）。

### 8. `GET /teams` → `get_teams()`
- **返回数据**：球队数组（id, logo, name, type），支持 `name` / `type` 过滤、分页（limit 0-500）。
- **后续用法**：
  - 按 `type=national` **批量预拉世界杯参赛队**的 logo/名称，而当前球队信息主要来自比赛同步的附带数据。
  - 为「球队库/搜索」页提供数据源。

### 9. `GET /teams/{id}` → `get_team_by_id()`
- **返回数据**：单个球队对象（id, logo, name, type）。
- **后续用法**：球队详情页/对阵页按需补充 logo 兜底；当比赛数据缺失球队 logo 时回源补全。

### 10. `GET /highlights` → `get_highlights()`
- **返回数据**：集锦数组（id, type, imgUrl, title, description, url, embedUrl, match, channel, source, category），可按 `matchId` / `leagueId` / `date` 过滤。
- **后续用法（高价值，明显功能缺口）**：
  - 在**比赛详情页 / 资讯流展示视频集锦**，这是面向球迷的核心内容，目前方法已封装却完全没用到。
  - 配合 A 层 5/6 做地理限制判断后展示。

### 11. `GET /lineups/{matchId}` → `get_lineups()`
- **返回数据**：`{ homeTeam, awayTeam }`，各含 `formation`、`initialLineup`（按阵型排布）、`substitutes`。
- **限制**：赛前 30 分 / 开赛 15 分内可用，每 10 分刷新。
- **后续用法**：
  - 比赛详情页展示**首发十一人 + 替补 + 阵型**。
  - 作为 AI 预测 prompt 的上下文输入（哪些核心球员首发，影响胜负判断）。

### 12. `GET /statistics/{matchId}` → `get_statistics()`
- **返回数据**：每队统计数组（`statistics` 含 `displayName` / `value`，如控球率、射门、xG 等）。
- **后续用法**：
  - 比赛详情页的「数据面板」；赛后复盘分析。
  - 当前 `box-score` 只给逐球员数据，缺**球队级比赛统计**，此接口正好补齐。

### 13. `GET /events/{id}` → `get_events()`
- **返回数据**：实时事件流（`team, time, type, playerId, player, assist` 等：进球、红黄牌、换人）。
- **限制**：每分钟刷新。
- **后续用法（高价值）**：
  - 实现**比赛实时追踪器**（进球/红牌即时推送），对世界杯这种集中观赛场景极具吸引力。
  - 与 `/odds` 的 `oddsType=live` 组合，做「比分+赔率」实时联动。

### 14. `GET /players` → `get_players()`
- **返回数据**：球员基础列表（id, name, fullName, logo），支持 `name` 过滤、分页（limit 0-1000）。
- **后续用法**：
  - 球员搜索 / 球员花名册目录。
  - 当前球员主数据来自 `box-score` 同步写入（`players.py` 注释已说明），此接口可补「按名字检索」能力。

### 15. `GET /players/{id}/statistics` → `get_player_statistics()`
- **返回数据**：球员赛季统计，按 `perCompetition` / `perClub` 聚合（进球、助攻、红黄牌等）。
- **后续用法**：
  - 球员详情页的「赛季数据」卡片（目前只用 `box-score` 的逐场数据，缺赛季汇总）。
  - 丰富预测上下文（如某队头号射手本赛季状态/伤停）。

---

## 四、面向世界杯预测项目的优先级建议

| 优先级 | 端点 | 理由 |
|--------|------|------|
| 🔴 高 | `/highlights` | 球迷向内容刚需，方法已就绪，直接接线即可上比赛详情页 |
| 🔴 高 | `/events/{id}` | 实现实时比分追踪，世界杯集中观赛场景核心体验 |
| 🔴 高 | `/bookmakers` | 替换硬编码博彩公司白名单，消除数据失准风险 |
| 🟠 中 | `/lineups/{matchId}` | 首发阵容展示 + 作为 AI 预测输入 |
| 🟠 中 | `/statistics/{matchId}` | 补齐球队级比赛数据面板 |
| 🟠 中 | `/players/{id}/statistics` | 球员赛季数据，丰富详情页与预测上下文 |
| 🟠 中 | `/teams` + `/countries` | 国家队/国家 logo 与筛选，世界杯场景实用 |
| 🟡 低 | `/leagues/{id}`、`/teams/{id}`、`/countries/{code}`、`/highlights/{id}`、`/bookmakers/{id}` | 元数据和兜底接口，按需接入 |

## 五、注意事项

1. **付费计划限制**：`/odds`（项目已用）与 `/highlights/geo-restrictions` 在 Basic/Free 不可用。若项目当前能拉到赔率，说明已具备付费资格；地理限制接口可放心试用。
2. **A 层需先补客户端方法**：`/bookmakers`、`/bookmakers/{id}`、`/countries/{code}`、`/leagues/{id}`、`/highlights/geo-restrictions/{id}`、`/highlights/{id}` 在 `highlightly.py` 中尚无封装，需先加方法再接线。
3. **B 层零成本**：其余 9 个方法已存在，仅需新增 service/api 调用即可，风险低。
