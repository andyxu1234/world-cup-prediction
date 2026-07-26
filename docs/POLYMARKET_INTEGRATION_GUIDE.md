# Polymarket Standalone 市场集成指南

## 概述

本指南帮助你完成 Polymarket Standalone 市场模块的部署和使用。这是一个独立的市场发现模块，用于 NO farming 等策略。

## 文件清单

### 后端文件

| 文件 | 说明 |
|------|------|
| `server/app/models/polymarket_standalone.py` | 数据库模型 |
| `server/alembic/versions/a1b2c3d4e5f6_*.py` | 数据库迁移 |
| `server/app/core/polymarket_standalone.py` | 核心市场发现逻辑 |
| `server/app/services/polymarket_standalone_sync.py` | 同步服务 |
| `server/app/api/v1/polymarket_standalone.py` | API 路由 |
| `server/app/api/router.py` | 更新：注册新路由 |
| `server/app/models/__init__.py` | 更新：注册新模型 |
| `server/app/core/scheduler.py` | 更新：添加定时任务 |
| `server/app/config.py` | 更新：添加配置选项 |
| `server/.env.example` | 更新：添加配置示例 |

### 前端文件

| 文件 | 说明 |
|------|------|
| `client/src/pages/polymarket/index.tsx` | 市场页面组件 |
| `client/src/pages/polymarket/index.scss` | 页面样式 |
| `client/src/services/polymarketApi.ts` | API 服务 |
| `client/src/app.config.ts` | 更新：注册新页面 |

### 文档

| 文件 | 说明 |
|------|------|
| `docs/POLYMARKET_STANDALONE.md` | 模块文档 |
| `docs/POLYMARKET_INTEGRATION_GUIDE.md` | 本指南 |

## 部署步骤

### 1. 运行数据库迁移

```bash
cd server
alembic upgrade head
```

这将创建 `polymarket_standalone_markets` 表。

### 2. 配置环境变量

在 `server/.env` 中添加：

```bash
# Polymarket Standalone 市场配置
POLYMARKET_MAX_ENTRY_PRICE=0.65
POLYMARKET_MAX_END_DATE_MONTHS=3
POLYMARKET_PROXY=http://127.0.0.1:10808  # 如果需要代理
```

### 3. 重启后端服务

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. 手动触发首次同步

```bash
curl -X POST http://localhost:8000/api/v1/polymarket/standalone/sync
```

或访问 API 文档：http://localhost:8000/docs

### 5. 访问前端页面

在小程序中访问 `/pages/polymarket/index` 页面。

## API 测试

### 获取市场统计

```bash
curl http://localhost:8000/api/v1/polymarket/standalone/stats
```

### 获取市场列表

```bash
curl "http://localhost:8000/api/v1/polymarket/standalone/markets?limit=10&sort_by=volume"
```

### 获取符合条件的市场

```bash
curl "http://localhost:8000/api/v1/polymarket/standalone/markets/eligible?max_price=0.65"
```

### 获取市场类别

```bash
curl http://localhost:8000/api/v1/polymarket/standalone/categories
```

## 定时任务

系统会在每天 03:00 自动同步市场数据。

查看定时任务状态：
```bash
# 查看日志
tail -f /tmp/worldcup-server.log | grep "Standalone"
```

手动触发同步：
```bash
curl -X POST http://localhost:8000/api/v1/polymarket/standalone/sync
```

## 数据结构

### StandaloneMarket

```python
@dataclass(frozen=True)
class StandaloneMarket:
    question: str           # 市场问题
    slug: str               # 唯一标识
    condition_id: str       # CLOB conditionId
    yes_token_id: str       # Yes 侧 token ID
    no_token_id: str        # No 侧 token ID
    yes_price: float        # Yes 价格 (0-1)
    no_price: float         # No 价格 (0-1)
    volume: float           # 成交量
    liquidity: float        # 流动性
    min_order_size: float   # 最小下单量
    end_date: str           # 结束日期
    end_ts: float           # 结束时间戳
    category: str           # 类别
    event_slug: str         # 事件 slug
```

## 过滤规则

市场必须满足以下条件才会被收录：

1. ✅ 二元 Yes/No 市场
2. ❌ 排除体育市场（足球、篮球、棒球等）
3. ❌ 排除加密市场（Bitcoin、Ethereum 等）
4. ❌ 排除金融市场（股票、外汇等）
5. ✅ 单事件市场（非 negRisk）
6. ✅ 未过期（结束时间在未来 3 个月内）
7. ✅ 无排除关键词

## 符合 NO farming 条件

市场满足以下条件时标记为 `is_eligible = true`：

- `no_price ≤ POLYMARKET_MAX_ENTRY_PRICE` (默认 65¢)

这些市场是 NO farming 策略的候选目标。

## 故障排查

### 同步失败

1. 检查网络连接
2. 检查代理配置 (`POLYMARKET_PROXY`)
3. 查看日志：`tail -f /tmp/worldcup-server.log | grep -i polymarket`

### 无数据显示

1. 确认已执行数据库迁移：`alembic upgrade head`
2. 确认已触发同步：`POST /api/v1/polymarket/standalone/sync`
3. 检查 API 响应：`GET /api/v1/polymarket/standalone/stats`

### 页面无法访问

1. 确认已注册页面：检查 `app.config.ts`
2. 重新编译前端：`npm run dev:h5`

## 与现有模块的区别

| 维度 | polymarket_events | polymarket_standalone |
|------|-------------------|----------------------|
| 数据范围 | 足球赛事 | 所有市场 |
| API 端点 | /events/keyset | /markets |
| 数据表 | polymarket_events, polymarket_markets | polymarket_standalone_markets |
| 用途 | 赔率对比 | NO farming 策略 |
| 关联本地比赛 | 是 | 否 |

## 后续扩展

可以基于此模块实现：

1. **NO farming 交易机器人**：自动买入符合条件的 NO
2. **价格监控**：监控 NO 价格变化
3. **套利提醒**：发现价格异常时推送通知
4. **数据分析**：分析历史市场数据

## 技术支持

如有问题，请查看：
- API 文档：http://localhost:8000/docs
- 日志文件：/tmp/worldcup-server.log
- 数据库：`SELECT * FROM polymarket_standalone_markets`
