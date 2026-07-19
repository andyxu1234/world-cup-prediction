# 数据中心改版计划：积分/球员榜/球队榜接入 Highlightly + 球队/球员详情页

> 目标：积分榜、球员榜、球队榜的数据统一改为从 Highlightly 拉取并落本地库；
> 用户点击球队或球员可进入详情页查看具体信息。
> 状态：规划稿，待 review 后实施。

---

## 一、当前系统状况（已核实）

| 模块 | 当前数据源 | 是否来自 Highlightly | 是否落库 |
|---|---|---|---|
| 积分榜 | `standings_calc.calculate_standings()` 从本地 `matches` 现算 | ❌ 本地现算 | 否 |
| 球队榜 | 复用积分榜数据，前端按指标重排（`client/.../data/index.tsx:175`） | ❌（依赖积分榜） | 否 |
| 球员榜 | 聚合 `match_player_stats`（来自 Highlightly `/box-score`） | ✅ | 是（明细表，已建表） |
| 球队统计/状态 | `/teams/statistics/{id}` + `/last-five-games`，存 `teams.season_stats`/`recent_form`（JSON） | ✅ | 是（JSON 列） |

- **详情页**：无。`client/src/pages` 下无 `team-detail` / `player-detail`，`data` 页三类行均不可点击。
- **Highlightly 客户端**（`server/app/core/highlightly.py`）：已有 `get_standings` / `get_team_statistics` / `get_last_five_games` / `get_box_score` / `get_teams`，**缺球员方法**（`get_players` / `get_player_by_id` / `get_player_statistics`）。
- **迁移状态**：`match_player_stats` 迁移（2026-07-17）已应用，表已存在。

## 二、关键约束（来自官方文档）

- `/players` 仅支持 `name/limit/offset`，**无 leagueId/teamId 过滤**。
- `/players/{id}/statistics` 返回 `perCompetition[].league`（字符串名）+ `season`（字符串），按名匹配联赛脆弱。
- 结论：**按联赛聚合球员榜最稳的来源仍是 box-score**（`match_player_stats` 已带 `league_id`）；`/players/{id}` 仅用于补充主数据（身高/位置/国籍等）。

---

## 三、目标方案

1. **积分榜 + 球队榜**：改用官方 `/standings` 落新表 `league_standings`；积分榜、球队榜都读此表（球队榜 = 按指标排序）。
2. **球员榜**：保留 box-score 来源，聚合快照到新表 `player_season_stats`；新增 `players` 主数据表（来自 `/players/{id}`）支撑详情页。
3. **详情页**：`team-detail` 读 `teams` 表（`season_stats`/`recent_form` 已存）；`player-detail` 读 `players` + `player_season_stats`。

---

## 四、数据库改动（3 张新表 + 迁移）

### 4.1 `league_standings`（积分榜/球队榜统一数据源）
来源：`GET /standings?leagueId&season`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | PK | |
| league_id | FK→leagues.id | |
| season | int | |
| group_name | varchar | 杯赛小组名 / 联赛名 |
| team_id | FK→teams.id (可空) | 本地队 id，匹配不到先用 highlightly_team_id 兜底 |
| highlightly_team_id | int | |
| team_name | varchar | 冗余，防队未入库 |
| team_logo | varchar | |
| position | int | 官方排名 |
| played / won / draw / lost | int | |
| goals_for / goals_against / goal_diff / points | int | goal_diff、points 可计算冗余存储 |
| home_won/draw/lost/GF/GA | int | 主场比赛拆分（丰富球队榜） |
| away_won/draw/lost/GF/GA | int | 客场比赛拆分 |
| fetched_at | datetime | |

唯一约束：`unique(league_id, season, group_name, highlightly_team_id)`

### 4.2 `players`（球员主数据）
来源：`GET /players/{id}`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | PK（=highlightly player id） | |
| name | varchar | |
| full_name | varchar | |
| logo | varchar | |
| position_main / position_secondary | varchar | profile.position.main/secondary |
| height | varchar | 形如 "1,86 m" |
| citizenship | varchar | 国籍 |
| birth_date | varchar | profile.birthDate |
| club | varchar | profile.club.current |
| fetched_at | datetime | |

### 4.3 `player_season_stats`（球员榜聚合快照）
来源：聚合 `match_player_stats`（box-score，已带 league_id）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | PK | |
| league_id | int | |
| season | int | 由 leagues 表 join 得到 |
| player_id | FK→players.id | =highlightly player id |
| player_name / player_logo | varchar | |
| team_name / team_logo | varchar | |
| position | varchar | |
| games_played / minutes_played | int | |
| goals / assists / yellow_cards / red_cards / second_yellow | int | |
| shots_total / shots_on_target | int | |
| fetched_at | datetime | |

唯一约束：`unique(league_id, season, player_id)`

> 实施：新增迁移文件 `server/alembic/versions/<rev>_add_data_detail_tables.py`，在 `server/app/models/__init__.py` 注册三个新模型。

---

## 五、后端改动

### 5.1 `server/app/core/highlightly.py`（新增球员方法）
- `get_players(name, limit, offset)` → `GET /players`
- `get_player_by_id(player_id)` → `GET /players/{id}`
- `get_player_statistics(player_id)` → `GET /players/{id}/statistics`

### 5.2 新 Service `server/app/services/standings_sync.py`
- `sync_league_standings()`：遍历 `is_active` 联赛，拉 `/standings`，upsert 进 `league_standings`；
  按 `highlightly_team_id`（或队名）解析本地 `team_id`。
- 保留 `standings_calc.calculate_standings()` 作为 `league_standings` 为空时的兜底。

### 5.3 扩展 `server/app/services/player_stats_sync.py`
- box-score 同步时顺带：① 写 `players` 主数据（`/players/{id}`）；② 重建 `player_season_stats` 聚合快照。
- 新增入口 `sync_player_master_and_season_stats()` 供 admin 全量触发。

### 5.4 改接口
- `server/app/api/v1/standings.py`
  - `/standings`：改为读 `league_standings` 表（空则兜底现算），响应 Schema `TeamStandingOut` 不变 → 前端无感。
  - `/standings/all`：改为跨活跃联赛聚合 `league_standings`。
- `server/app/api/v1/data.py`
  - `/player-rankings`：改为读 `player_season_stats` 表，`PlayerRankingItem` 可加字段（保持兼容）。

### 5.5 新接口
- `server/app/api/v1/teams.py`：`GET /teams/{team_id}` → 队信息 + `season_stats` + `recent_form`（`TeamDetailOut`）。
- `server/app/api/v1/players.py`：`GET /players/{player_id}?league_id=` → 主数据 + 该联赛统计（`PlayerDetailOut`）。
- `server/app/api/router.py`：注册 `teams` / `players` 路由。

### 5.6 `server/app/api/v1/admin.py`（新增同步入口）
- `POST /admin/standings/sync` → `standings_sync.sync_league_standings()`
- `POST /admin/players/sync` → `player_stats_sync.sync_player_master_and_season_stats()`
- 可选：在 `sync_pipeline` 比赛结束后追加 `sync_league_standings()`。

### 5.7 `server/app/core/cache.py`（可选）
- 新增 `team_detail_cache` / `player_detail_cache`（TTL 300s）。

### 5.8 新增 Schema
- `server/app/schemas/team_detail.py`：`TeamDetailOut`
- `server/app/schemas/player_detail.py`：`PlayerDetailOut`

---

## 六、前端改动

### 6.1 `client/src/services/api.ts`
- 新增 `getTeamDetail(teamId)`、`getPlayerDetail(playerId, leagueId)` 及类型 `TeamDetailOut` / `PlayerDetailOut`。
- 既有 `getStandings` / `getPlayerRankings` 保持不变。

### 6.2 `client/src/pages/data/index.tsx`
- 积分行、球队榜行 → `Taro.navigateTo({ url: '/pages/team-detail/index?id=' + t.team_id })`
- 球员榜行 → `Taro.navigateTo({ url: '/pages/player-detail/index?id=' + p.player_id + '&league_id=' + selectedLeagueId })`

### 6.3 新页面
- `client/src/pages/team-detail/index.tsx` + `index.scss`
  - 展示队徽、队名、FIFA 排名、小组、赛季统计（胜平负/进失球/主客场拆分）、最近 5 场战绩。
- `client/src/pages/player-detail/index.tsx` + `index.scss`
  - 展示头像、姓名、位置、身高、国籍、所属俱乐部、该联赛统计（进球/助攻/牌/出场/分钟）、可按联赛切换。

### 6.4 `client/src/app.config.ts`
- `pages` 数组追加 `pages/team-detail/index`、`pages/player-detail/index`。

---

## 七、实施顺序

1. **（前置）`alembic upgrade head`** —— 确认 `match_player_stats` 等现有表已建（已知已建好）。
2. 3 张新表模型 + 迁移 + `models/__init__.py` 注册。
3. `highlightly.py` 加 3 个球员方法。
4. `standings_sync.py` + 改 `standings.py` 读 `league_standings`。
5. 扩展 `player_stats_sync.py` + 改 `data.py` 读 `player_season_stats`。
6. `teams.py` / `players.py` 详情接口 + Schema + `router.py`。
7. `admin.py` 同步入口（+ 可选接入 pipeline）。
8. 前端 `api.ts` + `data/index.tsx` 跳转 + 两个详情页 + `app.config.ts`。
9. 再跑 `alembic upgrade head`（应用新表）→ 触发同步 → 联调。

---

## 八、风险与注意

- `league_standings.team_id`（本地）依赖 `stats_sync` 已通过 `/standings` 回填 `teams.highlightly_team_id`；匹配不到时先用 `highlightly_team_id` 兜底，详情页也能用。
- 球员榜坚持用 box-score 聚合（最稳），不用脆弱的 `/players/{id}/statistics` 联赛名匹配；`/players/{id}` 仅补主数据。
- `standings` 接口切换为读表后，需保证 `sync_league_standings()` 已跑过，否则走兜底现算（行为降级但不报错）。
- 新增表均为幂等 upsert，重复同步安全。
