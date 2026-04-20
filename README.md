# 世界杯 AI 预测大赛

让多个 AI 大模型同台竞技，预测 2026 FIFA 世界杯比赛结果。用户可以围观 AI 预测、参与投票、与 AI 一较高下，并通过社交分享扩大传播。

## 产品亮点

- **AI 对决**：5 个主流 AI 模型（DeepSeek、通义千问、智谱GLM、Claude、GPT）同台预测，看谁更准
- **人机大战**：用户投票预测，与 AI 模型一较高下
- **站队玩法**：选择支持的 AI 模型，模型战绩即你的战绩
- **打脸合集**：自动汇总高信心却翻车的预测，趣味十足
- **分享传播**：生成精美预测卡片，分享到微信

## 技术架构

```
微信小程序 (Taro + React + NutUI)
         │
         ▼
    Nginx 反向代理
         │
         ▼
    FastAPI (Python)
    ├── REST API (23 个端点)
    ├── APScheduler 定时任务
    ├── OfoxAI 统一网关 (5 个 AI 模型)
    ├── API-Football 比赛数据
    └── Pillow 分享卡片图片生成
         │
         ▼
    MySQL 8.0
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 小程序前端 | Taro 4 + React 18 + TypeScript + NutUI + Zustand |
| 后端框架 | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| 数据库 | MySQL 8.0 (asyncmy) |
| 缓存 | cachetools TTLCache |
| 定时任务 | APScheduler |
| HTTP 客户端 | httpx (async) |
| AI 网关 | OfoxAI (兼容 OpenAI 格式) |
| 比赛数据 | API-Football |
| 部署 | Docker Compose + Nginx |

## 项目结构

```
world-cup-prediction/
├── server/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 入口 + 生命周期
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 数据库连接
│   │   ├── deps.py          # 依赖注入
│   │   ├── models/          # ORM 模型 (7 张表)
│   │   ├── schemas/         # Pydantic 模型 (6 个)
│   │   ├── api/v1/          # 路由 (7 个文件, 23 端点)
│   │   ├── services/        # 业务逻辑 (7 个)
│   │   ├── core/            # 核心模块 (缓存/调度/AI/微信)
│   │   └── utils/           # 工具函数
│   ├── alembic/             # 数据库迁移
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
├── client/                  # Taro 小程序 (6 页面 + 3 Store + API 封装)
└── docs/                    # 项目文档
```

## 快速开始

### 环境要求

- Python 3.9+
- MySQL 8.0
- Docker & Docker Compose (可选，推荐)

### 本地开发

```bash
# 1. 进入后端目录
cd server

# 2. 创建虚拟环境 & 安装依赖
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入以下配置：
#   DB_PASSWORD=你的MySQL密码
#   DB_HOST=127.0.0.1          # 本地开发使用 127.0.0.1，Docker 部署使用 db
#   OFOXAI_API_KEY=你的OfoxAI密钥
#   API_FOOTBALL_KEY=你的API-Football密钥

# 4. 创建数据库
python -c "
import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='你的密码')
cur = conn.cursor()
cur.execute('CREATE DATABASE IF NOT EXISTS worldcup_prediction CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
conn.commit()
print('Database created')
conn.close()
"

# 5. 生成迁移脚本（首次或模型变更后）
alembic revision --autogenerate -m "init_tables"

# 6. 执行数据库迁移，建表
alembic upgrade head

# 7. 启动后端开发服务器
uvicorn app.main:app --reload --port 8000

# 访问 Swagger UI: http://localhost:8000/docs

---

# 8. 前端开发（另开终端）
cd client
npm install

# 开发模式（H5 浏览器预览，自带热更新）
npm run dev:h5
# 访问 http://localhost:10088（默认端口）

# 开发模式（微信小程序，配合微信开发者工具预览）
npm run dev:weapp
# 在微信开发者工具中打开 dist/ 目录

# 生产构建（H5）
npm run build:h5
# 输出到 client/dist/

# 生产构建（微信小程序）
npm run build:weapp
# 输出到 client/dist/
```

> **注意**：H5 模式调用本地后端时，需确保后端已配置 CORS（`server/app/main.py` 已添加），且浏览器控制台无跨域报错。微信开发者工具中需勾选「不校验合法域名」。

### Docker 部署

```bash
cd server

# 配置环境变量
cp .env.example .env
# 编辑 .env

# 一键启动
docker compose up -d

# 数据库迁移
docker compose exec api alembic upgrade head

# 查看日志
docker compose logs -f api
```

## 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DATABASE_URL` | MySQL 异步连接串 | `mysql+asyncmy://root:pwd@localhost:3306/worldcup` |
| `OFOXAI_API_KEY` | OfoxAI API 密钥 | `sk-xxx` |
| `API_FOOTBALL_KEY` | API-Football 密钥 | `xxx` |
| `WECHAT_APP_ID` | 微信小程序 AppID | `wx1234` |
| `WECHAT_APP_SECRET` | 微信小程序 AppSecret | `secret` |

## API 概览

基础路径：`/api/v1`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/matches` | 比赛列表 |
| GET | `/matches/{id}` | 比赛详情 |
| GET | `/matches/{id}/predictions` | 比赛 AI 预测 |
| GET | `/predictions/face-slaps` | 打脸合集 |
| GET | `/leaderboard/ai` | AI 模型排行 |
| GET | `/leaderboard/human` | 人机排行 |
| GET | `/leaderboard/stand` | 站队排行 |
| GET | `/long-term-predictions` | 冠亚季军预测 |
| POST | `/users/login` | 微信登录 |
| POST | `/users/vote` | 投票预测 |
| PUT | `/users/support` | 选择站队 |
| GET | `/users/profile` | 个人信息 |
| GET | `/share/card/{matchId}` | 分享卡片（JSON） |
| GET | `/share/card/{matchId}/image` | 分享卡片图片（PNG） |
| POST | `/admin/matches/sync` | 同步比赛数据 |
| POST | `/admin/predictions/generate` | 生成全部 AI 预测 |
| POST | `/admin/predictions/generate/{matchId}` | 生成单场 AI 预测 |
| POST | `/admin/predictions/evaluate` | 评估预测准确性 |

完整 API 文档请访问 `http://localhost:8000/docs`。

## AI 模型阵容

通过 OfoxAI 统一网关调用，一个 Key 覆盖全部模型：

| 模型 | 产地 | 说明 |
|------|------|------|
| DeepSeek V3.2 | 🇨🇳 | 国产性价比之王 |
| 通义千问 Qwen3.5 Plus | 🇨🇳 | 阿里旗舰大模型 |
| 智谱 GLM-5 | 🇨🇳 | 清华系，推理能力强 |
| Claude Sonnet 4.6 | 🇺🇸 | Anthropic 旗舰 |
| GPT-5.2 | 🇺🇸 | OpenAI 旗舰 |

## 数据库表

| 表名 | 说明 |
|------|------|
| `teams` | 球队信息 |
| `matches` | 比赛赛程与结果 |
| `ai_models` | AI 模型配置 |
| `predictions` | AI 单场预测 |
| `long_term_predictions` | AI 长期预测（冠亚季军） |
| `users` | 微信用户 |
| `user_votes` | 用户投票记录 |

## 开发进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1: 后端基础搭建 | ✅ 完成 | 项目骨架 + ORM + API 客户端 + 定时任务 |
| Phase 2: 后端 API + 业务逻辑 | ✅ 完成 | 23 端点 + 分享图片 + 种子数据 + Docker 部署 |
| Phase 3: 前端小程序 | ✅ 完成 | 6 页面 + 3 Store + 23 端点 API 封装 + 深色科技绿主题 |
| Phase 4: 部署 + 联调 + 上线 | 🔲 待开发 | Docker 部署 + 小程序审核 |

## 文档

- [产品需求文档](docs/REQUIREMENTS.md)
- [技术方案文档](docs/TECHNICAL_DESIGN.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [Phase 1 进度汇报](docs/PHASE1_REPORT.md)
- [Phase 2 进度汇报](docs/PHASE2_REPORT.md)
- [Phase 3 进度汇报](docs/PHASE3_REPORT.md)
- [UI 设计稿](docs/ui-design.html)

## License

MIT
