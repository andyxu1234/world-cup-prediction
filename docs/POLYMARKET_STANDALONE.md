# Polymarket Standalone 市场模块

## 概述

这是一个独立的 Polymarket 市场发现模块，用于 NO farming 等策略。它从 Polymarket Gamma API 拉取所有活跃市场，过滤后存储到独立的数据库表中。

与现有的 `polymarket_events` / `polymarket_markets` 表完全隔离，不关联本地比赛数据。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Polymarket Gamma API                      │
│                   /markets (活跃市场)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              core/polymarket_standalone.py                   │
│  - fetch_and_filter_markets()                               │
│  - 过滤: 排除加密/金融/体育、只保留二元 Yes/No、单事件        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│          services/polymarket_standalone_sync.py              │
│  - sync_standalone_markets()                                │
│  - 写入 polymarket_standalone_markets 表                     │
│  - 标记符合条件的市场 (NO ≤ max_entry_price)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            api/v1/polymarket_standalone.py                   │
│  - GET /markets - 市场列表                                   │
│  - GET /markets/eligible - 符合条件的市场                    │
│  - GET /categories - 市场类别                               │
│  - GET /stats - 统计信息                                    │
│  - POST /sync - 手动触发同步                                │
└─────────────────────────────────────────────────────────────┘
```

## 数据库表

### polymarket_standalone_markets

```sql
CREATE TABLE polymarket_standalone_markets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    slug VARCHAR(255) NOT NULL UNIQUE,      -- 市场唯一标识
    condition_id VARCHAR(80),                -- CLOB conditionId
    question TEXT,                           -- 市场问题
    yes_token_id VARCHAR(80),                -- Yes 侧 token ID
    no_token_id VARCHAR(80),                 -- No 侧 token ID
    yes_price FLOAT,                         -- Yes 价格 (0-1)
    no_price FLOAT,                          -- No 价格 (0-1)
    volume FLOAT,                            -- 累计成交量 (USD)
    liquidity FLOAT,                         -- 当前流动性 (USD)
    min_order_size FLOAT,                    -- 最小下单量
    category VARCHAR(200),                   -- 市场类别
    event_slug VARCHAR(255),                 -- 事件 slug
    end_date VARCHAR(50),                    -- 结束日期
    end_ts FLOAT,                            -- 结束时间戳
    is_eligible BOOLEAN DEFAULT FALSE,       -- 是否符合条件
    no_entry_price FLOAT,                    -- NO 入场价格
    last_checked_at DATETIME,                -- 最后检查时间
    last_synced_at DATETIME,                 -- 最后同步时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_slug (slug),
    INDEX idx_end_ts (end_ts),
    INDEX idx_category (category),
    INDEX idx_is_eligible (is_eligible)
);
```

## API 接口

### 获取市场列表

```
GET /api/v1/polymarket/standalone/markets
```

**参数：**
- `category` (可选): 按类别筛选
- `is_eligible` (可选): 只返回符合条件的市场
- `max_price` (可选): NO 价格上限 (0-1)
- `min_volume` (可选): 最小成交量
- `min_liquidity` (可选): 最小流动性
- `sort_by` (可选): 排序字段 (volume/liquidity/no_price/end_ts)
- `sort_order` (可选): 排序方式 (asc/desc)
- `limit` (可选): 返回数量 (默认 100)
- `offset` (可选): 偏移量

**响应：**
```json
{
  "markets": [
    {
      "id": 1,
      "slug": "will-bitcoin-hit-200k",
      "question": "Will Bitcoin hit $200k this week?",
      "yes_price": 0.12,
      "no_price": 0.88,
      "volume": 125000,
      "liquidity": 45000,
      "category": "Crypto",
      "is_eligible": false,
      ...
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

### 获取符合条件的市场

```
GET /api/v1/polymarket/standalone/markets/eligible
```

**参数：**
- `max_price` (可选): NO 价格上限 (默认 0.65)
- `min_volume` (可选): 最小成交量
- `sort_by` (可选): 排序字段
- `limit` (可选): 返回数量
- `offset` (可选): 偏移量

### 获取市场类别

```
GET /api/v1/polymarket/standalone/categories
```

**响应：**
```json
{
  "categories": [
    { "name": "Politics", "count": 45 },
    { "name": "Entertainment", "count": 30 },
    { "name": "Science", "count": 20 }
  ],
  "total_categories": 15
}
```

### 获取统计信息

```
GET /api/v1/polymarket/standalone/stats
```

**响应：**
```json
{
  "total_markets": 500,
  "active_markets": 450,
  "eligible_markets": 120,
  "avg_no_price": 0.72,
  "total_volume": 15000000
}
```

### 手动触发同步

```
POST /api/v1/polymarket/standalone/sync
```

**响应：**
```json
{
  "status": "ok",
  "message": "Standalone markets sync completed",
  "detail": {
    "total_fetched": 500,
    "total_filtered": 450,
    "new_markets": 100,
    "updated_markets": 350,
    "expired_removed": 50,
    "eligible_count": 120
  }
}
```

## 定时任务

每天 03:00 自动执行同步任务：

```python
scheduler.add_job(
    sync_standalone_markets,
    "cron",
    hour=3,
    minute=0,
    id="sync_standalone_markets",
    replace_existing=True,
)
```

## 配置

在 `.env` 文件中添加以下配置：

```bash
# NO farming 最高入场价格 (0-1)
POLYMARKET_MAX_ENTRY_PRICE=0.65

# 只保留未来 N 个月内结束的市场
POLYMARKET_MAX_END_DATE_MONTHS=3
```

## 前端页面

访问 `/pages/polymarket/index` 查看市场列表。

功能：
- 📊 实时统计（活跃市场数、符合条件数、平均 NO 价格、总成交量）
- 🏷️ 按类别筛选（Politics、Entertainment、Science 等）
- ✅ 只显示符合条件的市场（NO ≤ 65¢）
- 📈 按成交量/价格/流动性排序
- 🔄 手动触发同步

## 过滤规则

市场需要满足以下条件才会被收录：

1. **二元 Yes/No 市场**：只有两个结果（Yes 和 No）
2. **非体育市场**：排除 MLB、NBA、NFL、足球等
3. **非加密市场**：排除 Bitcoin、Ethereum 等
4. **非金融市场**：排除股票、外汇等
5. **单事件市场**：非 negRisk（多结果市场）
6. **未过期**：结束时间在未来 3 个月内
7. **无排除关键词**：标题/描述不含排除词

## 符合 NO farming 条件

市场符合 NO farming 条件当：
- `is_eligible = true`
- `no_price ≤ POLYMARKET_MAX_ENTRY_PRICE` (默认 65¢)

这些市场是 NO farming 策略的候选目标。

## 与现有模块的关系

| 模块 | 数据表 | 用途 | 数据源 |
|------|--------|------|--------|
| polymarket_sync | polymarket_events, polymarket_markets | 足球赛事赔率对比 | /events/keyset |
| polymarket_standalone | polymarket_standalone_markets | NO farming 策略 | /markets |

两个模块完全独立，互不影响。
