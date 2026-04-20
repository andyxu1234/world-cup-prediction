# 世界杯 AI 预测大赛 — 技术方案文档

## 1. 整体架构

```
┌─────────────────────────────────────────────────┐
│                  微信小程序 (Taro + React)         │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │ 首页 │ │ 预测 │ │ 排行 │ │ 用户 │ │ 分享 │  │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘  │
└─────┼────────┼────────┼────────┼────────┼──────┘
      │        │        │        │        │
      ▼        ▼        ▼        ▼        ▼
┌─────────────────────────────────────────────────┐
│              阿里云 ECS (2核2G)                    │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │         Nginx (反向代理 + 静态资源)            │  │
│  └──────────────────┬──────────────────────────┘  │
│                     ▼                              │
│  ┌─────────────────────────────────────────────┐  │
│  │       FastAPI (Python 3.12 + Uvicorn)        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │  │
│  │  │ REST API │ │ 定时任务  │ │ AI 调用网关  │ │  │
│  │  └──────────┘ └──────────┘ └──────────────┘ │  │
│  │  ┌──────────┐ ┌──────────────────────────┐  │  │
│  │  │ 本地缓存  │ │ APScheduler 定时调度     │  │  │
│  │  └──────────┘ └──────────────────────────┘  │  │
│  └────┬────────────────────────────────────────┘  │
│       ▼                                           │
│  ┌─────────┐                                      │
│  │ MySQL   │                                      │
│  │ (数据)  │                                      │
│  └─────────┘                                      │
└─────────────────────────────────────────────────┘
       │                │
       ▼                ▼
┌────────────┐   ┌──────────────┐
│ API-Football│  │   OfoxAI     │
│ (比赛数据)  │  │ (AI 统一网关) │
└────────────┘   └──────────────┘
```

## 2. 技术栈选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **小程序前端** | Taro 4 + React 18 + TypeScript | 跨端能力，后续可扩展 Web 版 |
| **UI 组件库** | NutUI (京东) | Taro 生态首选，组件丰富 |
| **状态管理** | Zustand | 轻量，适合小程序场景 |
| **后端框架** | FastAPI (Python 3.12) | 异步高性能，自动生成 API 文档，Python 生态做 AI 调用更自然 |
| **ASGI 服务器** | Uvicorn | 高性能异步服务器 |
| **ORM** | SQLAlchemy 2.0 + Alembic | Python ORM 首选，Alembic 做数据库迁移 |
| **数据库** | MySQL 8.0 | 成熟稳定，2核2G 资源友好 |
| **缓存** | cachetools (本地内存缓存) | 数据量极小（~620 条），无需 Redis |
| **定时任务** | APScheduler | 轻量级 Python 定时任务框架 |
| **HTTP 客户端** | httpx | 异步 HTTP 客户端，调用外部 API |
| **反向代理** | Nginx | SSL、静态资源、负载均衡 |
| **部署** | Docker + Docker Compose | 一键部署，环境一致性 |
| **进程管理** | Uvicorn (多 worker) | 生产部署标配 |

## 3. 数据量分析与缓存方案

### 3.1 数据量评估

| 数据类型 | 预估总量 | 内存占用 | 说明 |
|----------|---------|---------|------|
| 比赛 | ~104 条 | < 1MB | 整表缓存都行 |
| AI 预测 | ~520 条 | < 5MB | 比赛结束后不再变动 |
| 排行榜 | 5-10 条 | < 1KB | 简单聚合计算 |
| 用户投票 | 万级 | 查询时计算 | SQL 聚合即可 |

**结论**：全量缓存到 Python 进程内存也只需 < 10MB，无需 Redis，用 `cachetools` 的 TTLCache 即可。

### 3.2 缓存实现

```python
# app/core/cache.py
from cachetools import TTLCache
from functools import wraps

# 比赛列表缓存 5 分钟
match_cache = TTLCache(maxsize=100, ttl=300)
# 预测结果缓存 10 分钟（赛前不变，赛后更新一次即可）
prediction_cache = TTLCache(maxsize=500, ttl=600)
# 排行榜缓存 5 分钟
leaderboard_cache = TTLCache(maxsize=20, ttl=300)

def cached(cache_obj, key_fn=None):
    """通用缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs) if key_fn else f"{func.__name__}:{args}:{kwargs}"
            if key in cache_obj:
                return cache_obj[key]
            result = await func(*args, **kwargs)
            cache_obj[key] = result
            return result
        return wrapper
    return decorator
```

## 4. 数据库设计

### 4.1 球队表

```sql
CREATE TABLE teams (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,        -- 球队名称
  flag_url VARCHAR(500),             -- 国旗图片URL
  group_name VARCHAR(10),            -- 小组(A-H)
  fifa_rank INT,                     -- FIFA排名
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 比赛表

```sql
CREATE TABLE matches (
  id INT PRIMARY KEY AUTO_INCREMENT,
  match_day INT NOT NULL,            -- 比赛日
  round VARCHAR(50) NOT NULL,        -- 轮次: 小组赛/16强/8强/半决赛/决赛
  home_team_id INT NOT NULL REFERENCES teams(id),
  away_team_id INT NOT NULL REFERENCES teams(id),
  match_time DATETIME NOT NULL,      -- 开赛时间(UTC)
  venue VARCHAR(200),                -- 场地
  status ENUM('upcoming','live','finished') DEFAULT 'upcoming',
  home_score INT,                    -- 主队进球
  away_score INT,                    -- 客队进球
  result ENUM('home_win','draw','away_win'),  -- 赛果
  api_football_id INT,               -- API-Football 的比赛ID
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.3 AI 模型表

```sql
CREATE TABLE ai_models (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,         -- 展示名称
  model_id VARCHAR(100) NOT NULL,    -- OfoxAI 中的模型标识
  avatar_url VARCHAR(500),
  style_tags JSON,                   -- 风格标签
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 AI 单场预测表

```sql
CREATE TABLE predictions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  match_id INT NOT NULL REFERENCES matches(id),
  model_id INT NOT NULL REFERENCES ai_models(id),
  result ENUM('home_win','draw','away_win') NOT NULL,
  score_home INT,                    -- 预测主队进球
  score_away INT,                    -- 预测客队进球
  score_alt_home INT,                -- 备选比分-主队
  score_alt_away INT,                -- 备选比分-客队
  score_alt_prob DECIMAL(5,2),       -- 备选比分概率
  confidence TINYINT,                -- 信心指数 1-10
  analysis TEXT,                     -- 预测分析文字
  raw_response JSON,                 -- 原始返回
  is_correct_result BOOLEAN,         -- 胜负是否正确
  is_correct_score BOOLEAN,          -- 比分是否完全命中
  calculated_at DATETIME,            -- 计算正确性时间
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_match_model (match_id, model_id)
);
```

### 4.5 长期预测表

```sql
CREATE TABLE long_term_predictions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  model_id INT NOT NULL REFERENCES ai_models(id),
  champion_team_id INT REFERENCES teams(id),
  runner_up_team_id INT REFERENCES teams(id),
  third_place_team_id INT REFERENCES teams(id),
  analysis TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.6 用户表

```sql
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  openid VARCHAR(100) NOT NULL UNIQUE,
  nickname VARCHAR(100),
  avatar_url VARCHAR(500),
  supported_model_id INT REFERENCES ai_models(id),  -- 站队
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.7 用户投票表

```sql
CREATE TABLE user_votes (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL REFERENCES users(id),
  match_id INT NOT NULL REFERENCES matches(id),
  result ENUM('home_win','draw','away_win') NOT NULL,
  score_home INT,
  score_away INT,
  is_correct_result BOOLEAN,
  is_correct_score BOOLEAN,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_match (user_id, match_id)
);
```

## 5. 后端 API 设计

```
基础路径: /api/v1

// 比赛相关
GET    /matches                    获取比赛列表 (?round=小组赛&status=upcoming)
GET    /matches/:id                获取比赛详情(含各AI预测)

// 预测相关
GET    /matches/:id/predictions    获取某场比赛所有AI预测
GET    /predictions/compare/:id    预测对比视图数据
GET    /predictions/face-slaps     "被打脸"合集

// 排行榜
GET    /leaderboard/ai             AI模型排行榜 (?round=全部)
GET    /leaderboard/human          人机排行榜
GET    /leaderboard/stand          站队排行榜

// 长期预测
GET    /long-term-predictions      冠亚季军预测

// 用户相关
POST   /users/login                微信登录(code换openid)
POST   /users/vote                 用户投票预测
PUT    /users/support              选择站队
GET    /users/profile              用户信息

// 分享
GET    /share/card/:matchId        生成分享卡片数据

// 管理后台(内部)
POST   /admin/matches/sync         同步比赛数据
POST   /admin/predictions/generate 触发AI预测生成
POST   /admin/predictions/evaluate 评估预测准确性
```

## 6. 核心业务流程

### 6.1 AI 预测生成流程（定时任务）

```
每日 00:00 定时触发 (APScheduler)
  │
  ├── 1. 调用 API-Football 获取未来48h比赛列表
  │       └── 更新 matches 表
  │
  ├── 2. 遍历未来24h内的未预测比赛
  │       │
  │       └── 对每个AI模型:
  │             │
  │             ├── 构建 Prompt（含两队信息、历史交锋、FIFA排名等）
  │             ├── 调用 OfoxAI API (httpx 异步，兼容 OpenAI 格式)
  │             ├── 解析 JSON 响应
  │             └── 存入 predictions 表
  │
  └── 3. 缓存结果到本地 TTLCache
```

### 6.2 预测评估流程（比赛结束后）

```
每 30 分钟轮询 (APScheduler)
  │
  ├── 1. 调用 API-Football 获取已结束比赛的结果
  │
  ├── 2. 更新 matches 表 (status=finished, 比分, result)
  │
  ├── 3. 批量评估 predictions
  │       ├── is_correct_result = (预测胜负 == 实际胜负)
  │       └── is_correct_score = (预测比分 == 实际比分)
  │
  ├── 4. 更新排行榜本地缓存
  │
  └── 5. 生成"被打脸"数据(置信度高但预测错误)
```

### 6.3 AI Prompt 模板

```
你是一位足球分析专家，请预测以下世界杯比赛的结果。

比赛信息：
- 比赛：{home_team} vs {away_team}
- 轮次：{round}
- 场地：{venue}

球队信息：
- {home_team}：FIFA排名 #{home_rank}，近期战绩 {home_recent_form}
- {away_team}：FIFA排名 #{away_rank}，近期战绩 {away_recent_form}

历史交锋：{head_to_head}

请严格按照以下JSON格式输出预测结果，不要输出其他内容：
{
  "result": "home_win|draw|away_win",
  "score": { "home": 0, "away": 0 },
  "score_alt": { "home": 0, "away": 0, "probability": 0.0 },
  "confidence": 5,
  "analysis": "50-150字的预测分析"
}
```

## 7. 项目结构

### 7.1 整体目录

```
world-cup-prediction/
├── client/                          # Taro 小程序
├── server/                          # FastAPI 后端
├── docs/                            # 文档
└── scripts/                         # 部署脚本
```

### 7.2 前端 (client/)

```
client/
├── src/
│   ├── pages/
│   │   ├── index/               # 首页(今日比赛)
│   │   ├── match/               # 比赛详情+AI预测
│   │   ├── leaderboard/         # 排行榜
│   │   ├── profile/             # 个人中心
│   │   ├── face-slap/           # 打脸合集
│   │   └── share/               # 分享卡片
│   ├── components/              # 公共组件
│   ├── stores/                  # Zustand 状态
│   ├── services/                # API 请求
│   └── utils/
├── package.json
└── config/                      # Taro 编译配置
```

### 7.3 后端 (server/)

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置(环境变量)
│   ├── database.py                 # SQLAlchemy 连接
│   ├── deps.py                     # 依赖注入
│   │
│   ├── models/                     # SQLAlchemy ORM 模型
│   │   ├── team.py
│   │   ├── match.py
│   │   ├── ai_model.py
│   │   ├── prediction.py
│   │   ├── long_term_prediction.py
│   │   ├── user.py
│   │   └── user_vote.py
│   │
│   ├── schemas/                    # Pydantic 请求/响应模型
│   │   ├── match.py
│   │   ├── prediction.py
│   │   ├── leaderboard.py
│   │   ├── user.py
│   │   └── share.py
│   │
│   ├── api/                        # 路由
│   │   ├── v1/
│   │   │   ├── matches.py
│   │   │   ├── predictions.py
│   │   │   ├── leaderboard.py
│   │   │   ├── users.py
│   │   │   ├── share.py
│   │   │   └── admin.py
│   │   └── router.py              # 路由聚合
│   │
│   ├── services/                   # 业务逻辑
│   │   ├── match_sync.py           # API-Football 数据同步
│   │   ├── ai_predictor.py         # AI 预测生成
│   │   ├── prediction_evaluator.py # 预测评估
│   │   ├── leaderboard_calc.py     # 排行榜计算
│   │   └── share_card.py           # 分享卡片生成
│   │
│   ├── core/                       # 核心模块
│   │   ├── cache.py                # 本地缓存
│   │   ├── scheduler.py            # APScheduler 定时任务
│   │   ├── ofoxai.py               # OfoxAI 统一网关客户端
│   │   ├── api_football.py         # API-Football 客户端
│   │   └── wechat.py               # 微信登录
│   │
│   └── utils/
│       └── prompt_builder.py       # Prompt 构建工具
│
├── alembic/                        # 数据库迁移
│   ├── env.py
│   └── versions/
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 8. Docker 部署方案

### 8.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 8.2 docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: mysql:8.0
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: worldcup_prediction
    ports:
      - "127.0.0.1:3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    command: >
      --innodb-buffer-pool-size=256M
      --max-connections=50
      --character-set-server=utf8mb4
    mem_limit: 400m

  api:
    build: .
    restart: always
    environment:
      DATABASE_URL: mysql+asyncmy://root:${DB_PASSWORD}@db:3306/worldcup_prediction
      OFOXAI_API_KEY: ${OFOXAI_API_KEY}
      API_FOOTBALL_KEY: ${API_FOOTBALL_KEY}
      WECHAT_APP_ID: ${WECHAT_APP_ID}
      WECHAT_APP_SECRET: ${WECHAT_APP_SECRET}
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      - db
    mem_limit: 400m

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    mem_limit: 50m

volumes:
  mysql_data:
```

### 8.3 部署命令

```bash
# 在服务器上
git clone <repo> && cd world-cup-prediction/server

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入：
#   DB_PASSWORD — 数据库密码
#   OFOXAI_API_KEY — OfoxAI API Key
#   API_FOOTBALL_KEY — API-Football Key
#   WECHAT_APP_ID / WECHAT_APP_SECRET — 微信小程序凭证

# 一键启动
docker compose up -d

# 查看日志
docker compose logs -f api

# 数据库迁移
docker compose exec api alembic upgrade head

# 更新部署
git pull && docker compose up -d --build
```

## 9. 服务器资源规划（2核2G）

| 组件 | 内存占用 | 说明 |
|------|---------|------|
| MySQL 8.0 | ~350MB | buffer_pool=256M + 连接池 |
| FastAPI (2 workers) | ~150MB | uvicorn + Python |
| Nginx | ~20MB | - |
| 系统 + 余量 | ~480MB | 充足 |
| **合计** | **~1GB** | 比使用 Redis 方案省约 200MB |

> 若后续用户量增长，优先扩容到 2核4G。

## 10. Python 核心依赖

```
# Web 框架
fastapi==0.115.0
uvicorn[standard]==0.30.0

# 数据库
sqlalchemy[asyncio]==2.0.35
asyncmy==0.2.9
alembic==1.13.0

# 缓存
cachetools==5.5.0

# HTTP 客户端
httpx==0.27.0

# 定时任务
apscheduler==3.10.4

# 数据验证
pydantic==2.9.0
pydantic-settings==2.5.0

# 微信小程序
wechatpy==2.1.0

# 图片生成(分享卡片)
Pillow==10.4.0

# 工具
python-dotenv==1.0.1
loguru==0.7.2
```

## 11. AI 模型网关 — OfoxAI

### 11.1 为什么选择 OfoxAI

| 对比项 | OfoxAI | 硅基流动 + OpenRouter 双网关 |
|--------|--------|---------------------------|
| API Key 数量 | 1 个 | 2 个 |
| 网络要求 | 国内直连 | OpenRouter 需代理 |
| 模型覆盖 | 国内外 100+ 模型 | 各自覆盖一部分 |
| API 格式 | 兼容 OpenAI/Claude/Gemini | 各自兼容 OpenAI |
| 维护复杂度 | 低（单网关） | 高（双网关+降级逻辑） |
| 降级策略 | 不需要 | 需要跨网关降级 |

**OfoxAI 优势**：一个 Key、一个 base_url、国内直连，覆盖 GPT/Claude/Gemini/DeepSeek/Qwen/GLM 等全部主流模型，且支持多种 LLM 协议（OpenAI/Claude/Gemini），无需代理。

### 11.2 模型阵容

国内外模型混搭，增加对比话题性：

| OfoxAI model_id | 展示名称 | 产地 | 说明 |
|-----------------|---------|------|------|
| `deepseek/deepseek-v3.2` | DeepSeek | 🇨🇳 | 国产性价比之王 |
| `bailian/qwen3.5-plus` | 通义千问 | 🇨🇳 | 阿里旗舰大模型 |
| `z-ai/glm-5` | 智谱GLM | 🇨🇳 | 清华系，推理能力强 |
| `anthropic/claude-sonnet-4.6` | Claude | 🇺🇸 | Anthropic 旗舰 |
| `openai/gpt-5.2` | GPT | 🇺🇸 | OpenAI 旗舰 |

### 11.3 OfoxAI 客户端实现

```python
# app/core/ofoxai.py
import httpx
from loguru import logger

class OfoxAIClient:
    """OfoxAI 统一网关客户端 — 兼容 OpenAI Chat Completions 格式"""

    BASE_URL = "https://api.ofox.ai/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """调用 OfoxAI Chat Completions API"""
        resp = await self.client.post("/chat/completions", json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        logger.info(f"OfoxAI [{model}] response length: {len(content)}")
        return content

    async def predict_match(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        """单场预测便捷方法：构建 messages 并解析 JSON 响应"""
        import json
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self.chat_completion(model=model, messages=messages)
        # 尝试解析 JSON（AI 可能返回 markdown 代码块包裹的 JSON）
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(content)
```

### 11.4 调用示例

```python
# 在 ai_predictor.py 中使用
from app.core.ofoxai import OfoxAIClient

ofoxai = OfoxAIClient(api_key=settings.OFOXAI_API_KEY)

# 所有模型走同一个 base_url，只需切换 model 参数
result = await ofoxai.predict_match(
    model="deepseek/deepseek-v3.2",
    system_prompt="你是一位足球分析专家...",
    user_prompt="请预测阿根廷 vs 法国的比赛..."
)

result = await ofoxai.predict_match(
    model="anthropic/claude-sonnet-4.6",
    system_prompt="你是一位足球分析专家...",
    user_prompt="请预测阿根廷 vs 法国的比赛..."
)
```

## 12. API Key 申请流程

### 12.1 OfoxAI（AI 模型统一网关）

1. 访问 https://ofox.ai/ → 注册账号
2. 点击 "Get API Key" → 创建密钥
3. 免费计划包含 10+ 免费模型，付费按量计费（Pro 计划无月费）
4. 保存 Key
5. 验证：`curl https://api.ofox.ai/v1/models -H "Authorization: Bearer YOUR_KEY"`

**费用参考**（OfoxAI 按 token 计费，以下为单次预测约 500 input + 200 output tokens 估算）：

| 模型 | Input 价格 | Output 价格 | 520次预估费用 |
|------|-----------|------------|-------------|
| DeepSeek V3.2 | $0.29/M | $0.43/M | ~$0.15 |
| Qwen3.5 Plus | $0.40/M | $2.40/M | ~$0.70 |
| GLM-5 | $1.00/M | $3.20/M | ~$1.15 |
| Claude Sonnet 4.6 | $3.00/M | $15.00/M | ~$4.50 |
| GPT-5.2 | $1.75/M | $14.00/M | ~$3.85 |
| **合计** | | | **~$10.35** |

> **注意**：OfoxAI 国内可直连，无需配置代理。

### 12.2 API-Football（比赛数据）

1. 访问 https://www.api-football.com/ → 注册
2. 免费计划：**100次/天**，足够 MVP（每日同步1-2次比赛数据）
3. 付费计划：$9.99/月，10000次/天
4. 获取 Key 后验证：`curl https://v3.football.api-sports.io/status -H "x-apisports-key: YOUR_KEY"`
5. 世界杯相关 Endpoints：
   - `/fixtures` — 赛程与比分
   - `/fixtures/headtohead` — 历史交锋
   - `/teams` — 球队信息
   - `/standings` — 积分榜

## 13. 里程碑

2026 世界杯开赛时间：**6月11日**，按当前日期（4月9日）有约 9 周时间。

| 阶段 | 时间 | 目标 |
|------|------|------|
| **P0 基础搭建** | 第 1-2 周 | 项目脚手架、数据库建表、Docker 部署、API Key 就位 |
| **P1 核心功能** | 第 3-4 周 | 比赛同步、AI 预测生成、预测展示、排行榜 |
| **P2 用户功能** | 第 5-6 周 | 微信登录、投票、站队、人机排行 |
| **P3 传播功能** | 第 7-8 周 | 分享卡片、打脸合集、UI 打磨 |
| **P4 上线** | 第 9 周 | 内测、Bug 修复、小程序审核、正式上线 |
