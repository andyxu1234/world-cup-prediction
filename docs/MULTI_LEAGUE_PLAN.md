# 多联赛改造实施计划

## 改造目标

在影子库 `football_prediction` 上完成多联赛支持改造，让小程序能支持英超、西甲、德甲、意甲、法甲、欧冠、欧联等多个赛事。

## 前置条件

- ✅ 影子库 `football_prediction` 已创建并复制生产数据
- ✅ `docs/multi_league_migration.sql` 已执行（leagues 表已建、teams/matches/long_term_predictions 已加 league_id）
- ✅ 本地后端 `.env` 已切换到影子库

---

## Phase 1：后端 ORM 模型 + Alembic 迁移（预计 0.5 天）

### 1.1 新增 League 模型
- **文件**：`server/app/models/league.py`（新建）
- **内容**：`League` ORM 模型，对应 `leagues` 表
- **注册**：在 `server/app/models/__init__.py` 中导出

### 1.2 改造现有模型加 league_id
- `server/app/models/team.py`：加 `league_id` 字段 + relationship
- `server/app/models/match.py`：加 `league_id` 字段 + relationship
- `server/app/models/long_term_prediction.py`：加 `league_id` 字段 + relationship

### 1.3 生成 Alembic 迁移脚本
```bash
cd server
alembic revision --autogenerate -m "add leagues table and multi-league support"
```
- 检查生成的迁移脚本，确保与已执行的 SQL 一致
- **注意**：因为影子库已经手动执行了 SQL，alembic 会检测到表已存在，需要特殊处理：
  - 方案 A：手动修改 `alembic_version` 表，标记为已迁移
  - 方案 B：先 `alembic stamp head`（标记当前状态），再让后续新迁移正常工作
- **采用方案 B**：`alembic stamp head`，让 alembic 认为当前已是最新版本

### 1.4 验证
- `alembic current` 显示最新版本
- 后端能正常启动，ORM 能正确读写 league_id

---

## Phase 2：后端配置 + Highlightly 客户端改造（预计 0.5 天）

### 2.1 改造 `server/app/config.py`
- 移除写死的 `HIGHLIGHTLY_LEAGUE_ID` 和 `HIGHLIGHTLY_SEASON`（或保留作为默认值，但不再强制使用）

### 2.2 改造 `server/app/core/highlightly.py`
- `HighlightlyClient` 不再在 `__init__` 写死 `league_id` / `season`
- 改成方法参数传入：
  ```python
  async def get_matches(self, league_id: int, season: int, date=None, ...):
  ```
- 新增 `get_leagues()` 方法（用于查询 Highlightly 支持的联赛列表）
- `get_all_world_cup_matches` 改名为 `get_all_matches_by_league(league_id, season)`

### 2.3 验证
- 调用 `get_all_matches_by_league(33973, 2026)` 能返回英超比赛数据

---

## Phase 3：后端同步服务改造（预计 1 天）

### 3.1 改造 `server/app/services/match_sync.py`
- `sync_matches()` 改为 `sync_matches(league_id=None)`
  - `league_id=None`：遍历所有 `is_active=True` 的联赛逐个同步
  - `league_id=具体值`：只同步指定联赛
- `_upsert_match()` 加 `league_id` 参数，写入 `matches.league_id`
- `_upsert_team()` 加 `league_id` 参数，写入 `teams.league_id`

### 3.2 改造 `server/app/services/sync_pipeline.py`
- `sync_matches_and_respond()` 遍历活跃联赛，逐个调用 `sync_matches(league_id)`
- 每个联赛同步完后，事件驱动下游（H2H、stats、评估）

### 3.3 改造 `server/app/core/scheduler.py`
- `sync_matches_and_respond` 任务保持 30 分钟一次，内部遍历所有活跃联赛
- `generate_predictions` 任务保持每日 01:00，内部遍历所有活跃联赛的未预测比赛

### 3.4 验证
- 手动触发 `POST /admin/matches/sync`，确认能同步多个联赛
- 检查影子库 `matches` 表出现英超/西甲等比赛数据

---

## Phase 4：后端 API 改造（预计 1 天）

### 4.1 新增联赛接口
- **文件**：`server/app/api/v1/leagues.py`（新建）
- **接口**：
  - `GET /leagues` — 返回所有联赛列表（含 is_active 状态）
  - `GET /leagues/{id}` — 返回单个联赛详情
- **注册**：在 `server/app/api/router.py` 中注册

### 4.2 改造现有接口加 league_id 筛选
- `GET /matches` — 加 `league_id` 可选参数
- `GET /matches/{id}` — 响应里包含 `league_id` 和 `league` 信息
- `GET /matches/stats` — 加 `league_id` 可选参数（按联赛统计）
- `GET /matches/home-tabs` — 加 `league_id` 参数，按联赛返回不同 Tab 配置
- `GET /predictions/face-slaps` — 加 `league_id` 可选参数
- `GET /predictions/match/{matchId}` — 响应里包含 league 信息
- `GET /predictions/compare/{matchId}` — 同上

### 4.3 改造排行榜接口
- `GET /leaderboard/ai` — 加 `league_id` 可选参数（不传=全局排行）
- `GET /leaderboard/ai/{modelId}` — 加 `league_id` 参数
- `GET /leaderboard/human` — 加 `league_id` 可选参数

### 4.4 改造积分榜接口
- `GET /standings` — 加 `league_id` 必填参数
- 五大联赛是单组积分榜，世界杯是多组，响应结构需兼容

### 4.5 改造用户接口
- `GET /users/votes` — 加 `league_id` 可选参数
- `GET /users/profile` — 响应里可按联赛分类统计

### 4.6 改造 Schema
- `server/app/schemas/match.py`：`MatchOut` 加 `league_id` + `league` 字段
- 新建 `server/app/schemas/league.py`：`LeagueOut` schema

### 4.7 验证
- `curl /api/v1/leagues` 返回 8 个联赛
- `curl /api/v1/matches?league_id=2` 返回英超比赛
- Swagger UI 所有接口参数正确

---

## Phase 5：前端改造（✅ 已完成）

> 实施说明：
> - 新增 `useLeagueStore`（`currentLeagueId` 持久化到本地存储；`fetchLeagues` 只保留 `is_active` 联赛，默认选中第一个）。
> - 新增 `LeagueSwitcher` 组件，已接入首页 / 排行榜 / 打脸合集页顶部。
> - `api.ts` 全量补齐 `league_id` 参数（matches/stats/home-tabs/standings/face-slaps/leaderboard/ai-detail/profile/votes）+ 新增 `getLeagues`。
> - 首页 Hero 标题、总场次、积分榜（cup 多组 / league 单组）均按当前联赛动态渲染。
> - 比赛详情页展示联赛名称与 logo；AI 详情页跟随排行榜的联赛筛选。
> - ⚠️ 默认联赛由「世界杯」变为首个活跃联赛（世界杯 is_active=False，不在切换器内）。

### 5.1 新增联赛切换器组件
- **文件**：`client/src/components/LeagueSwitcher/`（新建）
- **功能**：首页顶部横向滚动的联赛 Tab，点击切换当前联赛
- **状态管理**：在 `client/src/stores/index.ts` 加 `currentLeagueId` 状态

### 5.2 改造首页 `client/src/pages/index/`
- 顶部加 `LeagueSwitcher` 组件
- 所有 API 调用传入 `currentLeagueId`
- Tab 配置改为从后端 `/matches/home-tabs?league_id=X` 动态获取
- 积分榜样式适配单组（五大联赛）和多组（世界杯/欧冠小组赛）

### 5.3 改造比赛详情页 `client/src/pages/match-detail/`
- 显示联赛名称
- API 调用适配

### 5.4 改造排行榜页 `client/src/pages/leaderboard/`
- 顶部加联赛筛选器
- API 调用传入 `league_id`
- 默认显示「全部」排行，可选按联赛筛选

### 5.5 改造打脸合集页 `client/src/pages/face-slap/`
- API 调用加 `league_id` 参数
- 可选加联赛筛选

### 5.6 改造个人中心 `client/src/pages/profile/`（✅ 已完成）
- 投票历史页 `vote-history` 接入 `LeagueSwitcher` + `league_id` 过滤（后端 `/users/votes` 已支持），命中率统计随联赛切换自动重算。
- `VoteHistoryItem` 增加 `league_name`，卡片标题显示所属联赛（如「小组赛第1轮 · 英超」）。
- 战绩统计按联赛分类：通过 vote-history 页命中率统计实现；profile 顶部三项（已预测/胜负正确/比分命中）保持全局口径——若 profile 传 `league_id` 会让服务端用联赛维度覆盖 `user.total_votes`，进而影响分享文案等全局逻辑，故不做此覆盖。

### 5.7 改造 API 封装 `client/src/services/api.ts`
- `getMatches(params)` 的 `params` 加 `league_id`
- 新增 `getLeagues()` 接口
- 其他接口按需加 `league_id` 参数

### 5.8 验证
- 首页切换联赛，比赛列表正确变化
- 排行榜按联赛筛选正常
- 投票历史按联赛筛选正常

---

## Phase 6：AI 预测改造（✅ 已完成）

### 6.1 改造 `server/app/services/ai_predictor.py`
- `generate_predictions()` 批量模式查询 `Match.status==upcoming` 且未来 3 天内比赛，**天然覆盖所有联赛**（同步只同步活跃联赛，故 upcoming 比赛均属活跃联赛，无需额外过滤）。
- 多联赛已在数据流中自动支持，无需改变遍历逻辑。

### 6.2 改造 `server/app/utils/prompt_builder.py`
- `SYSTEM_PROMPT` 由"世界杯"泛化为通用足球分析说明。
- `build_user_prompt` 新增 `league_name` 参数，单场 Prompt 加入「联赛：xxx」行。
- `build_summary_prompt` 新增 `league_name` 参数，汇总 Prompt 开头标注「比赛（联赛）：A vs B」。
- `build_long_term_prompt` 新增 `league_name` 参数（冠军预测，当前未调用，消除硬编码）。

### 6.3 改造 `server/app/services/prediction_graph.py`
- `load_match` 批量/单场查询均 `selectinload(Match.league)`，序列化 `match_data_list` 携带 `league_name`。
- `parallel_predict` / `retry_failed` 加载比赛时预加载 league，调用 `build_user_prompt` 传入联赛名。
- `aggregate` 调用 `build_summary_prompt` 传入 `league_name`。

### 6.4 验证
- 后端 `prompt_builder.py` / `prediction_graph.py` py_compile 通过。
- 手动触发预测生成后，确认 Prompt 含正确联赛名、可为各联赛比赛生成预测（需 3.10+ 环境 + 已同步联赛数据）。

---

## Phase 7：积分榜计算改造（7.1 ✅ 已完成 / 7.2 待确认）

### 7.1 改造 `server/app/services/standings_calc.py`（✅ 已在 Phase 4 完成）
- 已去掉写死的世界杯 8 组逻辑，改为根据联赛 `type` 动态计算：
  - `cup` 类型：只统计 `round contains "Group Stage"` 的小组赛，按球队 `group_name` 多组展示。
  - `league` 类型：查询该联赛全部已结束比赛，单组积分榜（以联赛 `cn_name` 为组名）。
- 统一按 `Match.league_id` 过滤；前端 `StandingsOut.type` 区分布局（Phase 5 已消费）。

### 7.2 改造积分榜同步（⏸ 待决策，未做）
现状：积分榜是**实时基于本地 `matches` 表结果计算**（不落地存储）。
- 方向 A（保持现状）：依赖同步的比赛结果本地计算。需确保各联赛比赛结果同步完整（尤其联赛类需全量赛程）。
- 方向 B（拉取官方积分榜）：从 Highlightly `/standings?leagueId=X&season=Y` 拉取真实积分榜，需新增 client 方法、standings 存储表与同步服务，前端展示切换为读取存储。
- 两市不同联赛的积分榜结构差异较大，建议先确认产品意图（本地计算 / 官方拉取）再动手。

---

## Phase 8：端到端测试 + 生产切换（预计 1 天）

### 8.1 影子环境端到端测试
- 同步英超数据 → 生成预测 → 用户投票 → 比赛结束评估 → 排行榜更新
- 全流程跑通

### 8.2 生产切换
- 参考 `docs/SHADOW_DB_MIGRATION.md` Step 4
- 低峰期操作，先迁移后部署

---

## 工作量汇总

| Phase | 内容 | 预计工时 |
|-------|------|---------|
| 1 | ORM 模型 + Alembic | 0.5 天 |
| 2 | 配置 + Highlightly 客户端 | 0.5 天 |
| 3 | 同步服务 | 1 天 |
| 4 | API 接口 | 1 天 |
| 5 | 前端改造 | 2-3 天 |
| 6 | AI 预测 | 0.5 天 |
| 7 | 积分榜 | 0.5 天 |
| 8 | 测试 + 切换 | 1 天 |
| **总计** | | **7-8 天** |

## 执行顺序

严格按 Phase 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 顺序执行。
每个 Phase 完成后验证，确认无问题再进入下一个 Phase。

## 风险点

1. **Highlightly API 配额**：多联赛同步会增加 API 调用量，需确认配额充足
2. **AI 预测成本**：多联赛比赛量大，OfoxAI 调用费用会增加
3. **前端兼容性**：世界杯期间的用户数据不能丢，历史投票/预测要保留
4. **积分榜差异**：不同联赛积分榜结构不同，需充分测试
