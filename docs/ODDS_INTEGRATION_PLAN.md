# 赔率（Odds）模块集成计划书

> 版本：v1.0 ｜ 日期：2026-07-21
> 范围：**仅赛前（prematch）赔率**，**不做 live 赔率**，**不改动前端**（赔率数据不进入现有小程序/前端页面）。
> 后续如有需要，再做独立 web 展示页（不在本次范围）。

---

## 1. 背景与目标

- 数据源：Highlightly Football API 的 `/odds` 端点（用户账号为 **PRO** 计划，该付费端点可用）。
- 目标：把指定比赛的赛前赔率落库，供后续分析 / 独立 web 页使用。
- 非目标：live 赔率、前端展示、预测模型融合（本次均不做）。

---

## 2. API 分析（Highlightly `/odds`）

| 项 | 内容 |
|----|------|
| 端点 | `GET https://soccer.highlightly.net/odds` |
| 认证 | 请求头 `x-rapidapi-key`（复用现有 `HIGHLIGHTLY_API_KEY`） |
| 数据窗口 | 赛前 7 天 ~ 赛后 28 天 |
| `oddsType` | `prematch`（默认）/ `live` —— 本次只用 `prematch` |
| 主查询参数 | `matchId` / `date` / `leagueId` / `bookmakerId` 等（至少一项） |

**响应结构（核心）**
```json
{
  "data": [
    {
      "matchId": 884822928,
      "odds": [
        {
          "bookmakerId": 1,
          "bookmakerName": "Stake.com",
          "type": "prematch",
          "market": "Full Time Result",
          "values": [ { "odd": 6.6, "value": "Home" } ]
        }
      ]
    }
  ],
  "pagination": { "totalCount": 490, "offset": 20, "limit": 100 }
}
```
颗粒度：**比赛 → 博彩公司 → 市场(market) → 选项(value) → odd 数值**。

**关键发现 / 优化点**
- `matchId` 直接对应 `matches.highlightly_id`（`server/app/models/match.py:38`，唯一索引），无需额外 ID 映射。
- 一次 `GET /odds?matchId=X` 会返回该场**所有**博彩公司的赔率 —— 所以**每场比赛只需 1 次调用**，与保留多少家博彩公司无关（客户端按 `is_active` 过滤即可）。72 场世界杯 ≈ 72 次/天，配额极低。
- `pagination.limit`：文档写默认 5、示例返回 100，存在不一致，**需实测确认是否需要翻页**。计划默认按单场一次拉全，若返回被截断再按 `offset/limit` 翻页。

**支持的市场（market）**：Full Time Result、Asian Handicap、Odd or Even、Total Goals、Both Teams to Score、Correct Score、First Team to Score、Total Cards、Clean Sheet、Total Corners。本次先落全部，前端/展示层再按需筛选。

---

## 3. 选定保留的博彩公司（10 家）

原则：**1 家 sharp 锚（Pinnacle，近零水差、代表真实概率）+ 若干高流水主流盘口（市场共识）**，其余小众盘噪音大、排除。

| highlightly_bookmaker_id | 名称 | 定位 |
|---|---|---|
| 4 | Pinnacle | 🔥 sharp 基准（锚） |
| 319 | bet365 | 全球交易量最大 |
| 11 | Marathonbet | 水差小，近 sharp |
| 3 | 1xBet | 高流水，覆盖广 |
| 10 | Betwinner | 高流水，欧亚覆盖好 |
| 66 | SBOBET | 亚洲盘（让球）权威 |
| 23 | Unibet | 欧洲主流（Kindred） |
| 55 | William Hill | 英国老牌 |
| 17 | Betway | 国际主流 |
| 9 | Bwin | 欧洲大陆代表 |

排除：尾部小众盘（id 在 `1.3xxxx` / `9xxxx` 段）及同集团重复项（Parimatch 32/74、Novibet 13/382、Dafabet 69/365 等）。
> 这 10 家作为 `bookmakers` 表种子，`is_active=True`；后续想扩只需改种子或加 `is_active` 标记。

---

## 4. 数据库设计

### 4.1 `bookmakers` 表（博彩公司字典）
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int PK | 自增 |
| `highlightly_bookmaker_id` | int **unique** | 对应 API `bookmakerId` |
| `name` | str | 博彩公司名 |
| `is_active` | bool default True | 是否参与拉取（装上述 10 家） |

### 4.2 `match_odds` 表（赔率明细）
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int PK | 自增 |
| `match_id` | int FK→`matches.id` | 通过 `highlightly_id` 关联 |
| `bookmaker_id` | int | API `bookmakerId`（冗余，便于直接筛） |
| `bookmaker_name` | str | 冗余存名 |
| `odds_type` | enum `prematch`/`live` | 本次全为 `prematch` |
| `market` | str | 如 `Full Time Result` |
| `value` | str | 如 `Home`/`Over`/`2 : 0` |
| `odd` | Float | 赔率数值 |
| `fetched_at` | DateTime | 抓取时间（赔率会变，留时间戳） |

**去重 / 唯一约束**：`(match_id, bookmaker_id, odds_type, market, value)` 建唯一索引，upsert 时按此键更新 `odd` / `fetched_at`。

### 4.3 关系
- `Match` 增加 `match_odds: Mapped[list["MatchOdd"]]` 反向关系（对齐 `match.py:51-59` 写法）。

---

## 5. 代码改动清单

### 5.1 新增 `server/app/models/odds.py`
两个模型 `Bookmaker` / `MatchOdd`，沿用现有 `Mapped`/`mapped_column` 风格（`Base` from `app.database`）。

### 5.2 `server/app/models/__init__.py`
注册 `Bookmaker`、`MatchOdd`（import 进 `__all__` 或直接 import，确保被 SQLAlchemy 元数据收集）。

### 5.3 新增 Alembic 迁移 `server/alembic/versions/<rev>_add_odds_tables.py`
- 建 `bookmakers` + `match_odds` 两张表 + 唯一索引。
- 种子数据：插入上述 10 家 `Bookmaker`（`highlightly_bookmaker_id` + `name` + `is_active=True`）。
- 参考既有迁移风格：`server/alembic/versions/h2i3j4k5l6m7_multi_league_support.py`。

### 5.4 扩展 `server/app/core/highlightly.py`（复用现有 `HighlightlyClient`）
新增方法（认证/header 完全复用，无需新配置）：
```python
async def get_odds(self, match_id: int, odds_type: str = "prematch",
                   limit: int = 100, offset: int = 0) -> dict:
    """GET /odds?matchId=...&oddsType=... 返回原始 JSON（含 pagination）"""
```
> 若实测发现单场返回被 `limit` 截断，则在 service 层按 `totalCount/limit` 翻页。

### 5.5 新增 `server/app/services/odds_service.py`
核心函数：
- `async def sync_odds_for_match(highlightly_id: int) -> int`
  - 调 `client.get_odds(match_id=highlightly_id)`，取 `data[0].odds`。
  - 按 `is_active` 的 10 家过滤（`bookmakerId` 白名单）。
  - upsert 进 `match_odds`（按唯一键更新）。
  - **单场失败仅记为失败、不抛异常**（对齐预测流程容错，见 §6）。
- `async def sync_all_upcoming_odds() -> dict`
  - 查 `matches` 中 `status='upcoming'`（及赛前 7 天内）的比赛。
  - 逐场调用 `sync_odds_for_match`，统计 success/failed。
  - 复用现有 `async_session_factory`，短生命周期 session（避免像预测流程那样占用连接）。

### 5.6 注册调度 `server/app/core/scheduler.py`
在 `start_scheduler()` 增加：
```python
from app.services.odds_service import sync_all_upcoming_odds
scheduler.add_job(
    sync_all_upcoming_odds, "cron",
    hour=4, minute=0, id="sync_odds", replace_existing=True,
)
```
- 每日 **04:00** 跑 prematch（在 01:00 预测、02:00 统计之后，且 matches 已由 30 分钟任务保持最新）。
- 配额：72 场 × 1 调用 ≈ 72 次/天，PRO 计划（7500/天）余量充足。

### 5.7 （可选）`server/app/services/sync_pipeline.py`
在 `sync_matches_and_respond` 的"新增比赛"分支里，对新比赛额外触发 `sync_odds_for_match`，做到新增比赛即时带赔率。可选，先不做也不影响每日 04:00 全量补齐。

---

## 6. 容错与一致性设计

- 单场 `get_odds` 异常 / JSON 解析失败：catch 后计入 `failed`，**不中断其他比赛**（与 `prediction_graph.parallel_predict` 的容错思路一致）。
- 网络/超时：复用 `ofoxai` 已调大的超时习惯；`HighlightlyClient` 若有自有 timeout 也建议放宽（赔率接口一般快，可不改）。
- `fetched_at` 时间戳：用于识别过期赔率；同一唯一键再次抓取时更新 `odd`/`fetched_at`（幂等 upsert）。

---

## 7. 不在本次范围（后续）

- **独立 web 展示页**：用户考虑后续单独做，不进现有 Taro 小程序 / 前端。
- **live 赔率**：每 10 分钟刷新，需额外调度与配额评估。
- **赔率→概率换算**：如用 Pinnacle 反推隐含概率、市场共识均值、与 AI 预测对比等（分析层，可后续叠加）。

---

## 8. 待确认 / 风险

| 项 | 说明 | 处理 |
|----|------|------|
| `limit` 分页 | 文档与示例不一致（5 vs 100） | 实测单场返回是否完整；不完整则在 service 翻页 |
| PRO 配额 | 赔率端点为付费，确认 PRO 档额度 | 已确认 tier=PRO，72 次/天远低于上限 |
| 字段对齐 | API `market`/`value` 字符串需与展示层约定 | 本次全量落库，展示时再映射 |

---

## 9. 落地步骤建议（执行顺序）

1. `models/odds.py` + `__init__.py` 注册
2. Alembic 迁移 + 10 家种子
3. `highlightly.py` 加 `get_odds()`
4. `odds_service.py`（sync + upsert）
5. `scheduler.py` 注册每日 04:00
6. 本地 `curl` 实测 `/odds?matchId=<某场>` 验证结构与分页，再决定翻页逻辑
7. 跑一次 `sync_all_upcoming_odds` 验证落库
