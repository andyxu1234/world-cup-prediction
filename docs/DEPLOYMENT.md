# 部署指南

## 架构概览

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│   API       │────▶│   MySQL     │
│   :80       │     │   :8000     │     │   :3306     │
│  反向代理    │     │  FastAPI    │     │  数据持久化   │
└─────────────┘     └─────────────┘     └─────────────┘
     容器                容器                容器
```

- **MySQL** — 数据库，数据通过 Docker Volume 持久化
- **API** — FastAPI 后端，容器启动时自动执行数据库迁移
- **Nginx** — 反向代理，统一入口（小程序也可直连 API 的 8000 端口）

前端（微信小程序）不在 Docker 中部署，小程序端直接请求后端 API。

---

## 前置条件

- Docker >= 20.10
- Docker Compose >= 2.0
- 服务器至少 1GB 内存

---

## 快速部署

### 1. 准备配置文件

```bash
cd server
cp .env.example .env
```

编辑 `.env`，填入真实密钥：

```env
# ── 数据库（必须修改） ──
DB_PASSWORD=你的数据库密码

# ── OfoxAI 统一 AI 网关（必须修改） ──
OFOXAI_API_KEY=你的_ofoxai_api_key

# ── Highlightly 比赛数据源（可选，不填则无法同步比赛数据） ──
HIGHLIGHTLY_API_KEY=你的_highlightly_key

# ── 微信小程序（必须修改，否则微信登录不可用） ──
WECHAT_APP_ID=你的小程序_appid
WECHAT_APP_SECRET=你的小程序_appsecret

# ── JWT 密钥（生产环境务必修改为随机字符串） ──
SECRET_KEY=随机生成的长字符串
```

生成随机 SECRET_KEY：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. 一键启动

```bash
docker compose up -d --build
```

### 3. 查看启动日志

```bash
docker compose logs -f api
```

正常输出应包含：

```
=== World Cup Prediction API Entry Point ===
[1/3] Waiting for MySQL at db:3306 ...
  MySQL is ready (3s)
[2/3] Running database migrations...
  Migrations done
[3/3] Starting API server...
```

### 4. 验证服务

```bash
# 健康检查
curl http://localhost/health

# API 文档
# 浏览器访问 http://你的服务器IP/docs
```

---

## 容器启动流程

API 容器启动时，`entrypoint.sh` 自动执行以下步骤：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1/3 | 等待 MySQL 就绪 | `mysqladmin ping`，最多等待 60 秒 |
| 2/3 | 执行数据库迁移 | `alembic upgrade head`，创建/更新所有表 |
| 3/3 | 启动 API 服务 | `uvicorn` 2 worker 进程 |

> 首次部署时，需通过管理接口或手动 SQL 导入初始数据（AI 模型、球队等）。

---

## 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DB_PASSWORD` | ✅ | - | MySQL root 密码 |
| `DB_HOST` | ❌ | `127.0.0.1` | 数据库地址（Docker 内自动设为 `db`） |
| `DB_PORT` | ❌ | `3306` | 数据库端口 |
| `DB_NAME` | ❌ | `worldcup_prediction` | 数据库名 |
| `DB_USER` | ❌ | `root` | 数据库用户 |
| `OFOXAI_API_KEY` | ✅ | - | OfoxAI AI 网关密钥 |
| `OFOXAI_BASE_URL` | ❌ | `https://api.ofox.io/v1` | AI 网关地址（注意是 `ofox.io`，非 `ofox.ai`） |
| `HIGHLIGHTLY_API_KEY` | ✅ | - | 比赛数据源密钥（无则无法同步比赛/积分榜/球员/赔率） |
| `WECHAT_APP_ID` | ✅ | - | 微信小程序 AppID |
| `WECHAT_APP_SECRET` | ✅ | - | 微信小程序 AppSecret |
| `SECRET_KEY` | ❌ | 内置默认值 | JWT 签名密钥，**生产环境务必更换** |

---

## 常用运维命令

### 服务管理

```bash
# 启动
docker compose up -d --build

# 停止
docker compose down

# 重启单个服务
docker compose restart api

# 查看所有服务状态
docker compose ps

# 查看资源占用
docker stats
```

### 日志查看

```bash
# 实时跟踪 API 日志
docker compose logs -f api

# 实时跟踪 MySQL 日志
docker compose logs -f db

# 最近 100 行日志
docker compose logs --tail 100 api
```

### 数据库操作

```bash
# 进入 MySQL 命令行
docker compose exec db mysql -uroot -p你的密码 worldcup_prediction

# 手动执行迁移
docker compose exec api alembic upgrade head
```

### 数据备份与恢复

```bash
# 导出数据库
docker compose exec db mysqldump -uroot -p你的密码 worldcup_prediction > backup.sql

# 恢复数据库
docker compose exec -T db mysql -uroot -p你的密码 worldcup_prediction < backup.sql
```

---

## 微信小程序配置

小程序端需要将 API 地址配置为你的服务器地址。修改 `client/src/services/api.ts`：

```typescript
const BASE_URL = process.env.NODE_ENV === 'production'
  ? 'https://你的域名/api/v1'    // ← 修改为你的服务器地址
  : ...
```

**微信小程序要求**：
- 生产环境必须使用 HTTPS
- 需在[微信公众平台](https://mp.weixin.qq.com/) → 开发管理 → 开发设置 中添加服务器域名到 `request合法域名`
- 开发阶段可在微信开发者工具中勾选「不校验合法域名」进行调试

---

## 生产环境 HTTPS 配置

### 方式一：使用 Nginx 容器（推荐）

1. 将 SSL 证书放到 `server/ssl/` 目录：

```
server/ssl/
├── cert.pem
└── key.pem
```

2. 修改 `docker-compose.yml`，取消 nginx 的 HTTPS 注释：

```yaml
nginx:
  ports:
    - "80:80"
    - "443:443"           # 取消注释
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
    - ./ssl:/etc/nginx/ssl:ro   # 取消注释
```

3. 修改 `nginx.conf`，启用 HTTPS：

```nginx
# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name 你的域名;
    return 301 https://$server_name$request_uri;
}

# HTTPS 服务
server {
    listen 443 ssl;
    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location /api/ {
        proxy_pass http://api:8000/api/;
        # ... 其他 proxy_set_header 保持不变
    }
}
```

4. 重启 nginx：

```bash
docker compose up -d --force-recreate nginx
```

### 方式二：使用云服务商负载均衡

在云服务商（腾讯云、阿里云等）的负载均衡层配置 HTTPS 证书，将 443 端口转发到服务器的 80 端口。此方式无需修改 nginx 配置。

---

## 更新部署

代码更新后重新构建部署：

```bash
cd server
git pull                          # 拉取最新代码
docker compose up -d --build api  # 仅重建 API 服务
```

如果数据库有新的迁移文件，API 容器重启时会自动执行 `alembic upgrade head`。

---

## 端口说明

| 服务 | 容器内端口 | 宿主机映射 | 说明 |
|------|-----------|-----------|------|
| MySQL | 3306 | 127.0.0.1:3306 | 仅本地可访问，外部不可直连 |
| API | 8000 | 127.0.0.1:8000 | 仅本地可访问，通过 Nginx 代理 |
| Nginx | 80 | 0.0.0.0:80 | 对外暴露的唯一端口 |

> MySQL 和 API 仅绑定 `127.0.0.1`，外部无法直接访问，只能通过 Nginx 代理。

---

## 故障排查

### API 容器启动失败

```bash
# 查看详细日志
docker compose logs api

# 常见原因：
# 1. .env 中缺少必填变量 → 补全后重新 docker compose up -d --build api
# 2. MySQL 未就绪 → 检查 db 容器状态: docker compose ps db
```

### MySQL 连接失败

```bash
# 检查 MySQL 容器状态
docker compose ps db
docker compose logs db

# 手动测试连接
docker compose exec db mysql -uroot -p你的密码 -e "SELECT 1"
```

### 数据库迁移报错

```bash
# 查看当前迁移版本
docker compose exec api alembic current

# 查看迁移历史
docker compose exec api alembic history

# 手动执行迁移（查看详细输出）
docker compose exec api alembic upgrade head
```

### 重置数据库（慎用）

```bash
# 删除所有数据并重建
docker compose down -v           # -v 会删除 mysql_data volume
docker compose up -d --build     # 重新创建
```

---

## 文件结构

```
server/
├── .dockerignore          # Docker 构建排除文件
├── .env                   # 环境变量（不入版本控制）
├── .env.example           # 环境变量模板
├── .gitattributes         # 确保 shell 脚本 LF 行尾
├── Dockerfile             # API 镜像构建
├── docker-compose.yml     # 编排配置
├── entrypoint.sh          # 容器启动脚本
├── nginx.conf             # Nginx 反向代理配置
├── alembic.ini            # 数据库迁移配置
├── alembic/               # 迁移文件
│   └── versions/          # 各版本迁移脚本
├── app/
│   └── ...
└── requirements.txt       # Python 依赖
```
