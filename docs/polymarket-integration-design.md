# Polymarket × Highlightly 赛事匹配 & AI 交易信号 — 设计 Brainstorm

> 目标：新增一个 job，从 Polymarket（Gamma API）拉取体育赛事，与本地 `matches`（来自 Highlightly）做匹配，
> 使每条 Polymarket 市场都能关联到本地比赛；后续用 AI 预测概率与 Polymarket 价格对比产生交易信号，去 Polymarket 上操作。
> 日期：2026-07-23

---

## 一、Polymarket 抓取逻辑（来自 `standalone_sports.py`，已理解）

- **接口**：`GET https://gamma-api.polymarket.com/events/keyset`
  - 参数：`closed=false`、`locale=en`、`series_id=<联赛ID>`、`limit=500`，游标 `cursor` 翻页。
  - 世界杯 `series_id = "11433"`；其余如 EPL=`10188`、La Liga=`10193` 等（见 `SPORT_CATEGORIES`）。
- **每个 event（赛事）字段**：
  - `title`：`"France vs. Argentina - Match Result"` / `"... - Over 2.5"` 等形式。
  - `slug`：事件 slug（可用于构造市场 URL）。
  - `endDate`：开赛时间（ISO，UTC，文件用它当 kickoff）。
  - `markets[]`：每个问题是一个 market，含 `question`、`conditionId`、`outcomes`(`comes`)、`clobTokenIds`、`outcomePrices`、`volume`、`liquidity`。
  - `sport`：含 `series`、`sport`、`image`(logo)、`resolution`(裁决 URL)。
- **解析方式**：
  - `_parse_teams_from_title` 用 `" vs. " / " vs " / " v " / " v. "` 切出主客队名。
  - `_classify_market_type` 把 market 分成 `matchResult` / `handicap` / `total` / `other`。
  - **可交易的最小单位 = `clobTokenId`**（每个 outcome 一个 token；二元市场即 yes/no 两个 token）。
- **可复用**：`fetch_series_events(series_id, name, session)`、`_parse_teams_from_title`、`_classify_market_type`、`_build_market` 都能直接搬过来。

---

## 二、匹配策略（Polymarket event → 本地 match）

### 2.1 联赛级（series → league）
- 建配置表/常量：`POLYMARKET_SERIES_TO_LEAGUE = {"11433": <worldcup_league_id>}`。
- 世界杯在本地只有 1 个 league 行（`leagues.highlightly_league_id` + `season`），先 1:1 即可，后续扩到其他联赛。

### 2.2 比赛级（event → match）
对每条 Polymarket event（base title = `主队 vs 客队`）：
1. 解析主客队名（`_parse_teams_from_title`）。
2. **队名归一化（关键难点）**：Polymarket 用国家名（可能 "USA" / "Korea Republic" / "England"），本地 `teams.name` 是英文但未必完全一致。需一张 **alias 表**（如 `USA↔United States`、`Korea Republic↔South Korea`）。可一次性由 `teams` 表手工/半自动建。
3. 在目标 league 的 `matches` 中按 `home_team.name(或alias) == 主 && away_team.name == 客` 找行。
4. **时间兜底**：`|matches.match_time − polymarket.endDate|` 在容忍窗口内（如 ±24h，世界杯全球同开赛，时间几乎一致）作为强确认，避免同名队误匹配。
5. 命中后把 `match_id` 写回 Polymarket 市场记录。

### 2.3 市场/Token 级
- 每个 market question → `market_type`（matchResult/handicap/total/other）。
- 每个 outcome → 一个可交易 token（`clobTokenId`）。
- 存：`condition_id`、`token_id`、`side`(yes/no)、`label`、`price`(yes 价)、`volume`、`liquidity`、`slug`、`event_slug`、`series_id`、`match_id`。

---

## 三、新增数据模型（建议）

### `polymarket_markets`（主表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| match_id | FK→matches.id (nullable) | 匹配到本地比赛后回填 |
| series_id | String | "11433" 等 |
| event_slug | String | |
| market_type | Enum | match_result/handicap/total/other |
| question | String | 原始问题 |
| outcome_label | String | "France" / "Draw" / "Over 2.5" |
| side | String | yes / no |
| condition_id | String | Polymarket 市场 ID |
| token_id | String | **clobTokenId，实际交易标的（唯一）** |
| yes_price | Float | 0–1，二元市场 no = 1−yes |
| volume / liquidity | Float | |
| raw_json | JSON | 原始 market blob |
| last_synced_at | DateTime | |
| created_at | DateTime | |

唯一约束建议 `(condition_id, token_id)` 或仅 `token_id`（每个 token 全局唯一）。

> 可选：`polymarket_events` 做 match 级分组（event_slug / title / start_ts / matched_match_id）。v1 可先不建，全部落 `polymarket_markets` 即可。

---

## 四、Job 设计（接入现有 `scheduler.py`）

参考现有 `sync_odds`(每6h) 与 `generate_predictions`(每天)。建议分成两个节奏：

1. **事件发现 + 匹配（低频，如每 6h / 每天）**
   - 调 `fetch_series_events` 拉配置的所有 series。
   - 解析队名 → alias 归一 → 匹配 `matches` → upsert `polymarket_markets`（含 `match_id` 链接）。
   - 新比赛（世界杯临近才开放市场）靠这个节奏捕获。
2. **价格刷新（高频，如每 15–30min，仅市场开放时）**
   - 对已有 token 行重拉 `outcomePrices` / `volume` / `liquidity`，更新 `yes_price` 等。
   - Polymarket 价格像赔率一样会动，AI vs 盘口对比依赖新鲜价格。

> 注意：抓取走 Gamma **只读** API，不涉及钱包/CLOB；与交易执行解耦。

---

## 五、AI → Polymarket 操作（后续，真正"操作"那一步）

> ⚠️ 这一步是**真金白银交易**，与前面只读 job 解耦。

流程：
1. 比赛预测生成后，对每条已匹配的 match：
   - 取 **AI 三方向概率** `P_ai(home/draw/away)`。
   - 取 Polymarket 隐含概率 = "Match Result" 市场各 token 的 `yes_price`。
2. 算 **edge = P_ai − P_poly**。
   - `edge > 阈值(如 0.08)` 且 AI confidence 高 → 信号：`买 YES`（被低估）或 `买 NO`（被高估）。
3. **执行**：用 trading-bot 仓库已有的 CLOB 下单基础设施（clob client / 钱包 / USDC）。
   - 本后端**只产出交易信号**（match_id / token_id / side / size / limit_price）写入信号表或队列，由 bot 消费；或调 bot 暴露的 API。
   - 需：仓位大小、单场最大敞口、滑点/价差处理、kill-switch。

### 5.1 关键前置：预测表需补"三方向概率"
当前 `predictions` 只存 `result`(winner) + `confidence` + `score_alt_prob`(单值)，**没有主/平/客的概率分布**。要算 edge 有两条路：
- **A（推荐）**：扩展 schema，让 AI 额外输出 `p_home / p_draw / p_away`（和为 1），存 `predictions` + 聚合到 `prediction_summaries`。提示词改造小，价值大。
- **B（v1 凑合）**：用 winner + confidence 近似映射成概率（如 confidence 8/10 → 该结果 0.7）。粗糙，仅做原型。

---

## 六、合规/风险提醒（务必先看清）

1. **交易是重风险，与 6.1.5 内容合规是两回事**：微信封的是"展示投注内容"；而**实际在 Polymarket 下单**是真实金融/加密活动。Polymarket ToS 限制美国居民；从中国大陆还有外汇/加密及赌博监管敞口。请**有意决策**，不要无意识踩线。
2. **别把 Polymarket 价格/交易动作暴露到公开 web/小程序**：那只会使 6.1.5 风险复发。应放在**私有侧**（类似现有 `/internal/odds` 令牌闸页面），仅自己/授权者可见。
3. 只读同步 job 本身合规风险低（只是拉公开数据存库）；风险集中在第五节的执行层。

---

## 七、待你拍板的决策点

1. **本次范围**：只做「只读同步 + 匹配」job？还是连「交易信号表/逻辑」骨架也一并搭？
2. **预测 schema**：是否接受扩展 `predictions` 增加三方向概率（方案 A）？还是 v1 先用 winner+confidence 近似（方案 B）？
3. **执行落点**：交易由 trading-bot 仓库执行——它是暴露 API 给我们调，还是我们只写信号表/队列让它来 poll？
4. **初始 series**：只世界杯 `11433`，还是把 `SPORT_CATEGORIES` 里已有 soccer 联赛（EPL/LaLiga…）也纳入？
5. **价格刷新节奏**：15min / 30min？
