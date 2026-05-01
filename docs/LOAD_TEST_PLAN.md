# Locust 压测方案

## 1. 概述

本文档为世界杯预测小程序后端服务设计基于 Locust 的压力测试方案，目标是验证 2核2G 阿里云服务器在真实流量下的承载能力、发现性能瓶颈、确定系统上限。

## 2. 服务器环境

| 项目 | 配置 |
|------|------|
| CPU | 2 核 |
| 内存 | 2 GB |
| 带宽 | 200 Mbps |
| 部署方式 | Docker Compose |
| 容器分配 | MySQL 400MB + FastAPI 400MB + Nginx 50MB |
| Uvicorn | 1 worker (async) |
| MySQL 连接池 | pool_size=5, max_overflow=10 (最大 15) |
| 缓存 | 内存 TTLCache (TTL 5-10min) |
| 限流 | 无 |

### 2.1 理论容量估算

| 瓶颈类型 | 估算值 | 说明 |
|----------|--------|------|
| 带宽 | ~5000 req/s | 假设平均响应 5KB，200Mbps ÷ 5KB |
| CPU (缓存命中) | ~200-500 req/s | 2核 async FastAPI，序列化 + 网络 IO |
| CPU (DB 查询) | ~100-300 req/s | 受连接池 15 限制，查询 ~50ms |
| 内存 | 约 1.15GB 可用 | 2GB - 容器分配 850MB - OS 开销 |

**结论**: CPU 和 MySQL 连接池是主要瓶颈，带宽不是问题。

## 3. 测试目标

1. **验证正常负载** 下 p95 响应时间 < 500ms
2. **找到系统拐点** — 错误率超过 1% 或 p95 超过 2s 时的并发数
3. **检查稳定性** — 持续负载下是否有内存泄漏或连接耗尽
4. **确认缓存效果** — 缓存命中率对吞吐量的影响

## 4. API 端点分类

### 4.1 压测范围 (用户可触发的接口)

| 端点 | 方法 | 缓存 TTL | 预期响应时间 |
|------|------|----------|-------------|
| `/api/v1/matches/stats` | GET | 5min | < 50ms |
| `/api/v1/matches` | GET | 5min | < 50ms |
| `/api/v1/matches/{id}` | GET | 5min | < 100ms |
| `/api/v1/predictions/match/{id}` | GET | 10min | < 100ms |
| `/api/v1/predictions/compare/{id}` | GET | 10min | < 100ms |
| `/api/v1/predictions/face-slaps` | GET | 10min | < 100ms |
| `/api/v1/leaderboard/ai` | GET | 5min | < 100ms |
| `/api/v1/leaderboard/human` | GET | 5min | < 100ms |
| `/api/v1/users/vote` | POST | - | < 200ms |
| `/api/v1/users/profile` | GET | 60s | < 100ms |
| `/api/v1/users/votes` | GET | 60s | < 100ms |
| `/health` | GET | 无 | < 10ms |
| `/cache-stats` | GET | 无 | < 10ms |

### 4.2 排除范围 (不纳入压测)

| 端点 | 原因 |
|------|------|
| `POST /users/login` | 调用微信外部 API |
| `POST /users/upload-avatar` | 文件上传，不同性能特征 |
| `POST /admin/*` | 管理后台操作，非用户流量 |
| `POST /cache/clear` | 管理操作 |
| `GET /fun-fact` | 调用 DeepSeek 外部 API |
| `GET /long-term-predictions` | 数据量极小，无需压测 |

## 5. 用户行为模型

### 5.1 用户类型分布

| 用户类型 | 权重 | 占比 | 行为特征 |
|----------|------|------|----------|
| BrowsingUser | 7 | 70% | 纯浏览：首页 → 比赛列表 → 比赛详情 → 预测 → 排行榜 |
| ActiveUser | 2 | 20% | 活跃用户：浏览 + 投票 + 查看个人资料 |
| HealthCheckUser | 1 | 10% | 健康检查：定期访问 /health |

### 5.2 请求权重分布

```
BrowsingUser (70%):
  /matches/stats          ×10  (首页最高频)
  /matches                ×8
  /matches/[id]           ×6
  /predictions/match/[id] ×5
  /predictions/compare    ×4
  /leaderboard/ai         ×3
  /leaderboard/human      ×2
  /face-slaps             ×2

ActiveUser (20%):
  /matches/[id]           ×5
  /leaderboard/ai         ×4
  /users/vote             ×3  (写操作)
  /users/profile          ×2
  /users/votes            ×2
  /predictions/match/[id] ×1

HealthCheckUser (10%):
  /health                 ×1
  /cache-stats            ×1
```

## 6. 测试场景

### 6.1 Smoke Test (冒烟测试)

**目的**: 验证所有接口正常工作，无报错。

```bash
locust -f locustfile.py --host=http://<SERVER_IP>:8000 \
  --headless -u 10 -r 2 -t 1m --csv=smoke
```

| 参数 | 值 |
|------|-----|
| 并发用户 | 10 |
| 启动速率 | 2 users/s |
| 持续时间 | 1 分钟 |
| 预期结果 | 错误率 0%，p95 < 200ms |

### 6.2 Normal Load (正常负载)

**目的**: 模拟日常访问量。

```bash
locust -f locustfile.py --host=http://<SERVER_IP>:8000 \
  --headless -u 50 -r 5 -t 10m --csv=normal
```

| 参数 | 值 |
|------|-----|
| 并发用户 | 50 |
| 启动速率 | 5 users/s |
| 持续时间 | 10 分钟 |
| 预期结果 | 错误率 < 0.1%，p95 < 300ms，CPU < 60% |

### 6.3 Peak Load (比赛日高峰)

**目的**: 模拟比赛日大量用户同时访问。

```bash
locust -f locustfile.py --host=http://<SERVER_IP>:8000 \
  --headless -u 200 -r 10 -t 15m --csv=peak
```

| 参数 | 值 |
|------|-----|
| 并发用户 | 200 |
| 启动速率 | 10 users/s |
| 持续时间 | 15 分钟 |
| 预期结果 | 错误率 < 1%，p95 < 1000ms，CPU < 85% |

### 6.4 Stress Test (压力测试)

**目的**: 找到系统极限，观察降级行为。

```bash
locust -f locustfile.py --host=http://<SERVER_IP>:8000 \
  --headless -u 500 -r 20 -t 10m --csv=stress
```

| 参数 | 值 |
|------|-----|
| 并发用户 | 500 |
| 启动速率 | 20 users/s |
| 持续时间 | 10 分钟 |
| 预期结果 | 找到错误率 > 1% 的拐点，记录此时并发数 |

### 6.5 Soak Test (浸泡测试)

**目的**: 长时间运行检测内存泄漏、连接耗尽。

```bash
locust -f locustfile.py --host=http://<SERVER_IP>:8000 \
  --headless -u 100 -r 10 -t 60m --csv=soak
```

| 参数 | 值 |
|------|-----|
| 并发用户 | 100 |
| 启动速率 | 10 users/s |
| 持续时间 | 60 分钟 |
| 预期结果 | 内存使用稳定，无连接泄漏，p95 无明显上升 |

## 7. 关键指标

### 7.1 Locust 指标

| 指标 | 正常 | 警告 | 危险 |
|------|------|------|------|
| Error Rate | < 0.1% | 0.1-1% | > 1% |
| p50 Response Time | < 100ms | 100-500ms | > 500ms |
| p95 Response Time | < 300ms | 300-1000ms | > 1000ms |
| p99 Response Time | < 500ms | 500-2000ms | > 2000ms |
| RPS (Requests/s) | 记录基线 | 下降 > 20% | 下降 > 50% |

### 7.2 服务器指标

| 指标 | 正常 | 警告 | 危险 |
|------|------|------|------|
| CPU Usage | < 60% | 60-85% | > 85% |
| Memory Usage | < 70% | 70-90% | > 90% |
| MySQL Connections | < 10 | 10-14 | 15 (池满) |
| Docker Container Memory | < limit | 接近 limit | OOM Killed |

## 8. 监控方法

### 8.1 服务器端监控

```bash
# 实时查看 Docker 容器资源使用
docker stats

# 查看系统资源
htop

# 查看 MySQL 连接数
mysql -e "SHOW STATUS LIKE 'Threads_connected';"

# 查看 Uvicorn 日志
docker logs -f <api_container_name> --tail 100

# 查看 Nginx 访问日志
docker logs -f <nginx_container_name> --tail 100
```

### 8.2 Locust Web UI

访问 `http://localhost:8089` 查看实时图表：
- 响应时间分布 (Response Times)
- 每秒请求数 (RPS)
- 用户数 (Users)
- 错误率 (Failures)

### 8.3 导出报告

```bash
# 生成 CSV 报告
locust -f locustfile.py --host=http://<SERVER_IP>:8000 \
  --headless -u 200 -r 10 -t 15m --csv=report

# 生成文件:
# report_stats.csv    - 汇总统计
# report_stats_history.csv - 历史数据
# report_failures.csv - 失败详情
# report_exceptions.csv - 异常详情
```

## 9. 压测执行步骤

### 9.1 测试前准备

```bash
# 1. 确保服务器正常运行
curl http://<SERVER_IP>:8000/health

# 2. 检查数据库有数据
curl http://<SERVER_IP>:8000/api/v1/matches/stats

# 3. 预热缓存 (请求几次主要接口)
for i in {1..5}; do
  curl -s http://<SERVER_IP>:8000/api/v1/matches > /dev/null
  curl -s http://<SERVER_IP>:8000/api/v1/leaderboard/ai > /dev/null
done

# 4. 记录基线指标
curl http://<SERVER_IP>:8000/cache-stats
ssh root@<SERVER_IP> "docker stats --no-stream"
```

### 9.2 执行顺序

```
Smoke Test (1min) → Normal Load (10min) → 等待 5min → Peak Load (15min) → 等待 5min → Stress Test (10min)
```

Soak Test 建议单独执行，不与其他场景叠加。

### 9.3 测试后分析

```bash
# 查看 Locust 生成的 CSV
cat report_stats.csv

# 检查服务器日志有无异常
ssh root@<SERVER_IP> "docker logs --tail 500 <api_container> 2>&1 | grep -i error"

# 检查 MySQL 慢查询
ssh root@<SERVER_IP> "docker exec <db_container> mysql -e 'SHOW PROCESSLIST;'"
```

## 10. 安装 Locust

```bash
# 安装 (建议在本地机器运行，不在服务器上)
pip install locust

# 验证安装
locust --version
```

> **注意**: 压测客户端应在本地机器运行，通过网络向服务器发请求。不要在被测服务器上运行 Locust，否则会争抢资源。

## 11. 预期结果分析

### 11.1 缓存效果

- 缓存命中时 (5-10min TTL 内重复请求): 响应时间极快 (< 50ms)
- 缓存未命中时 (首次请求或 TTL 过期): 需要查 MySQL，响应时间上升
- 每 5 分钟 APScheduler 缓存预热会刷新缓存，减少冷启动概率

### 11.2 MySQL 连接池

- 最大 15 连接 (5 pool + 10 overflow)
- 并发超过 15 时，新请求会等待连接释放
- 如果查询慢 (> 100ms)，15 连接最多支撑 ~150 req/s

### 11.3 内存压力

- 2GB 总内存，容器分配 850MB
- TTLCache 在内存中，数据量小 (< 10MB)
- 主要内存消耗: Python 进程 + MySQL buffer pool
- 并发高时需关注是否 OOM

### 11.4 可能的瓶颈点

1. **MySQL 连接池耗尽** — 并发 > 100 且查询慢时
2. **Uvicorn 单 worker CPU 打满** — 并发 > 200 且有计算密集操作时
3. **内存不足** — 长时间高并发导致 Python 进程内存增长
4. **Nginx 代理超时** — 后端响应慢导致 Nginx 502/504

## 12. 优化建议 (根据压测结果)

如果压测发现瓶颈，可考虑的优化方向：

| 瓶颈 | 优化方案 |
|------|----------|
| CPU 打满 | 增加 Uvicorn workers (改为 2-4) |
| MySQL 连接池满 | 增大 pool_size 或引入 Redis 缓存 |
| 内存不足 | 升级到 4G 服务器或优化缓存策略 |
| 响应慢 | 检查慢查询、添加数据库索引 |
| 带宽不够 | 启用 Nginx gzip 压缩 (已配置) |
