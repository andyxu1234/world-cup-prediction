# 影子数据库迁移计划

## 背景

当前生产环境运行的是世界杯预测小程序，数据库 `worldcup_prediction` 承载着所有生产数据。
为了支持五大联赛、欧冠、欧联等多赛事扩展，需要对数据库 schema 进行较大改造。
直接在生产库上改风险太大，因此先创建一套影子数据库 `football_prediction`，在其中完成所有改造和验证，最后再切换生产。

## 目标

1. 在同一个 MySQL 实例中创建影子库 `football_prediction`
2. 复制生产库的 schema + 全量数据到影子库
3. 配置本地后端连接影子库进行开发
4. 生产环境完全不动，零风险

---

## Step 1：在生产 MySQL 创建影子库并复制数据

SSH 登录生产服务器，执行以下操作。

### 1.1 创建影子库

```sql
mysql -u root -p -e "CREATE DATABASE football_prediction CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 1.2 导出生产库 schema + 数据

```bash
mysqldump -u root -p \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  worldcup_prediction > /tmp/worldcup_prediction_backup.sql
```

参数说明：
- `--single-transaction`：InnoDB 一致性快照，不锁表
- `--quick`：大表不缓存到内存，直接流式输出
- `--routines`：包含存储过程/函数（如果有）
- `--triggers`：包含触发器（如果有）

### 1.3 导入到影子库

```bash
mysql -u root -p football_prediction < /tmp/worldcup_prediction_backup.sql
```

### 1.4 验证数据完整性

```sql
-- 对比两个库的表数量
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'worldcup_prediction';

SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'football_prediction';

-- 逐表对比行数（关键表）
USE football_prediction;
SELECT 'teams' AS tbl, COUNT(*) AS cnt FROM teams
UNION ALL SELECT 'matches', COUNT(*) FROM matches
UNION ALL SELECT 'ai_models', COUNT(*) FROM ai_models
UNION ALL SELECT 'predictions', COUNT(*) FROM predictions
UNION ALL SELECT 'prediction_summaries', COUNT(*) FROM prediction_summaries
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'user_votes', COUNT(*) FROM user_votes
UNION ALL SELECT 'head_to_heads', COUNT(*) FROM head_to_heads
UNION ALL SELECT 'team_stats', COUNT(*) FROM team_stats
UNION ALL SELECT 'long_term_predictions', COUNT(*) FROM long_term_predictions
UNION ALL SELECT 'vip_members', COUNT(*) FROM vip_members;
```

对比生产库的同样查询，行数应完全一致。

### 1.5 清理备份文件

```bash
rm /tmp/worldcup_prediction_backup.sql
```

### 1.6 （可选）验证 alembic 版本表

```sql
USE football_prediction;
SELECT version_num FROM alembic_version;
```

应与生产库的 `alembic_version` 一致（当前最新版本号）。

---

## Step 2：配置本地后端连接影子库

### 2.1 修改本地 `server/.env`

将 `DB_NAME` 改为 `football_prediction`，其他保持生产配置：

```env
DB_PASSWORD=你的生产密码
DB_HOST=生产MySQL地址
DB_PORT=3306
DB_NAME=football_prediction
DB_USER=root

OFOXAI_API_KEY=你的key
HIGHLIGHTLY_API_KEY=你的key
WECHAT_APP_ID=你的appid
WECHAT_APP_SECRET=你的secret
```

> **注意**：如果生产 MySQL 不允许远程连接，需要通过 SSH 隧道访问：
> ```bash
> ssh -L 3306:127.0.0.1:3306 user@生产服务器IP -N
> ```
> 然后本地 `.env` 的 `DB_HOST` 填 `127.0.0.1`。

### 2.2 验证本地后端能连上影子库

```bash
cd server
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 启动后端
uvicorn app.main:app --reload --port 8000

# 另开终端验证
curl http://localhost:8000/api/v1/matches?limit=1
# 应返回影子库中的比赛数据
```

### 2.3 验证 alembic 状态

```bash
cd server
alembic current
# 应显示与生产一致的版本号

alembic heads
# 应显示最新版本
```

---

## Step 3：在影子库上进行改造

所有数据库改造都在影子库 + 本地代码分支上进行，生产完全不动。

### 3.1 创建开发分支

```bash
git checkout -b feature/multi-league
```

### 3.2 改造流程

1. 修改 ORM 模型（`server/app/models/`）
2. 生成 alembic 迁移脚本
   ```bash
   alembic revision --autogenerate -m "add leagues table and multi-league support"
   ```
3. 在影子库执行迁移
   ```bash
   alembic upgrade head
   ```
4. 修改业务代码（services、api）
5. 本地测试验证

### 3.3 改造过程中的注意事项

- **不要**在生产库上执行任何 `alembic upgrade`
- **不要**把 `.env` 的改动提交到 git（避免影响生产部署）
- 每次大改动前可以备份影子库：
  ```bash
  mysqldump -u root -p football_prediction > /tmp/fb_backup_$(date +%Y%m%d).sql
  ```
- 改坏了可以直接重建：
  ```bash
  mysql -u root -p -e "DROP DATABASE football_prediction; CREATE DATABASE football_prediction CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  mysql -u root -p football_prediction < /tmp/worldcup_prediction_backup.sql
  ```

---

## Step 4：改造完成后的生产切换

当影子库改造完成、本地测试通过后，按以下顺序切换生产环境。

### 4.1 切换前准备

1. 选择低峰期（建议凌晨 3-5 点，无比赛时段）
2. 通知用户（可选，通过小程序公告）
3. 备份生产库
   ```bash
   mysqldump -u root -p --single-transaction worldcup_prediction > /tmp/worldcup_production_backup_$(date +%Y%m%d).sql
   ```

### 4.2 切换步骤（严格按顺序）

```
1. 在生产库执行 alembic 迁移（加表/加字段，nullable 不锁表）
   cd server
   alembic upgrade head

2. 部署新版后端代码
   git pull
   ./restart.sh

3. 验证后端正常
   curl https://marathoninfo.top/health
   curl https://marathoninfo.top/api/v1/matches?limit=1

4. 提交小程序新版本审核

5. 审核通过后用户自动更新
```

### 4.3 回滚预案

如果切换后发现问题：

```bash
# 1. 代码回滚
git revert <commit-hash>
./restart.sh

# 2. 数据库回滚（如果迁移有问题）
alembic downgrade -1

# 3. 极端情况：恢复生产库备份
mysql -u root -p worldcup_prediction < /tmp/worldcup_production_backup_$(date +%Y%m%d).sql
```

### 4.4 切换后清理

确认生产稳定运行 1 周后，删除影子库：

```bash
mysql -u root -p -e "DROP DATABASE football_prediction;"
```

---

## 附：影子库与生产库对照表

| 项 | 生产库 | 影子库 |
|----|--------|--------|
| 数据库名 | `worldcup_prediction` | `football_prediction` |
| 用途 | 线上服务 | 开发测试 |
| 数据来源 | 用户实时产生 | 从生产复制 |
| 改造权限 | ❌ 不动 | ✅ 可任意改 |
| alembic 状态 | 当前版本 | 可自由 upgrade/downgrade |

## 附：常见问题

### Q：影子库的数据会和生产同步吗？
不会。影子库是一次性快照，复制后的改动不会自动同步。如需重新同步，重新执行 Step 1。

### Q：本地后端连影子库会影响生产吗？
不会。数据库完全独立，后端服务也是本地运行的，生产服务无感知。

### Q：如果生产 MySQL 不允许远程连接怎么办？
两种方案：
1. SSH 隧道（推荐）：`ssh -L 3306:127.0.0.1:3306 user@server -N`
2. 在生产服务器上跑第二个后端实例（8001 端口），连影子库，前端 H5 指向 8001

### Q：改造期间生产有新数据进来怎么办？
影子库是快照，不包含改造期间的新数据。切换生产时，alembic 迁移只改 schema 不改数据，生产原有数据不受影响。

---

## 检查清单

执行 Step 1 前确认：
- [ ] 已 SSH 登录生产服务器
- [ ] 确认 MySQL 有足够磁盘空间（影子库大小 ≈ 生产库大小）
- [ ] 确认 `mysqldump` 和 `mysql` 命令可用

执行 Step 2 前确认：
- [ ] 影子库已创建且数据完整
- [ ] 本地能连通生产 MySQL（直连或 SSH 隧道）
- [ ] 本地 `server/.env` 已备份原配置

执行 Step 4 前确认：
- [ ] 影子库改造完成且本地测试通过
- [ ] 已选择低峰期
- [ ] 已备份生产库
- [ ] 回滚预案已准备
