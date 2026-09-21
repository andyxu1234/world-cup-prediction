# -*- coding: utf-8 -*-
"""后端技术栈分层图生成器 (Style 1 Flat Icon)
输出 docs/diagrams/backend-stack.svg —— 与 frontend-stack.svg 同风格
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "backend-stack.svg"

BG = "#F8FAFC"
CONTAINER_STROKE = "#CBD5E1"
CONTAINER_FILL = "#FFFFFF"
TITLE = "#0F172A"
SUB = "#64748B"
BLUE = "#3B82F6"
GREEN = "#10B981"
PURPLE = "#8B5CF6"
ORANGE = "#F59E0B"
RED = "#EF4444"
CYAN = "#06B6D4"
PINK = "#EC4899"
GRAY = "#94A3B8"
FONT = "PingFang SC, Microsoft YaHei, sans-serif"

L = []


def add(s):
    L.append(s)


def box(x, y, w, h, title, sub, fill, stroke, fs=13.5, subfs=10):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    ty = y + (h / 2) - (6 if sub else 0)
    add(f'<text x="{x + w/2}" y="{ty}" fill="{TITLE}" font-size="{fs}" '
        f'font-weight="600" text-anchor="middle" font-family="{FONT}">{title}</text>')
    if sub:
        add(f'<text x="{x + w/2}" y="{y + h/2 + 14}" fill="{SUB}" font-size="{subfs}" '
            f'text-anchor="middle" font-family="{FONT}">{sub}</text>')


def container(x, y, w, h, label, color=CONTAINER_STROKE):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" '
        f'fill="{CONTAINER_FILL}" stroke="{color}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    add(f'<text x="{x + 14}" y="{y + 20}" fill="{color}" font-size="12.5" '
        f'font-weight="700" font-family="{FONT}">{label}</text>')


def varrow(x, y1, y2, color, label):
    add(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{color}" '
        f'stroke-width="1.8" marker-end="url(#arrow)"/>')
    if label:
        add(f'<text x="{x + 9}" y="{(y1 + y2)/2 + 4}" fill="{color}" font-size="11" '
            f'font-family="{FONT}">{label}</text>')


# ---- canvas ----
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 920" font-family="' + FONT + '">')
add(f'<rect x="0" y="0" width="960" height="920" fill="{BG}"/>')
add(f'<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="8" refY="3.5" '
    f'orient="auto"><path d="M0,0 L10,3.5 L0,7 Z" fill="{BLUE}"/></marker></defs>')
add(f'<text x="480" y="34" fill="{TITLE}" font-size="19" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">后端技术栈分层图</text>')
add(f'<text x="480" y="50" fill="{SUB}" font-size="11.5" text-anchor="middle" '
    f'font-family="{FONT}">FastAPI 异步 API 服务 · 自上而下 = 接入 → 应用 → 数据/AI → 外部依赖</text>')

# 1. 接入 / 部署层
container(60, 56, 840, 72, "接入 / 部署层")
box(72, 86, 280, 36, "Nginx", "反向代理 + SSL", GRAY, GRAY, fs=13)
box(368, 86, 320, 36, "Docker + compose", "python:3.12-slim · 400m", GRAY, GRAY, fs=12.5)
box(704, 86, 180, 36, "uvicorn", "ASGI 服务器", GRAY, GRAY, fs=13)

# 2. Web 框架与 API 层
container(60, 140, 840, 80, "Web 框架与 API 层")
box(72, 170, 360, 42, "FastAPI 0.115.0", "ASGI · /api/v1 路由聚合", BLUE, BLUE, fs=14)
box(448, 170, 240, 42, "CORS / StaticFiles", "全开跨域 · 头像/赔率页", BLUE, BLUE, fs=12)
box(704, 170, 180, 42, "lifespan", "启动缓存预热+调度", BLUE, BLUE, fs=12.5)

# 3. 数据访问层
container(60, 232, 840, 96, "数据访问层")
box(72, 262, 250, 42, "SQLAlchemy 2.0", "asyncio ORM", GREEN, GREEN, fs=13)
box(336, 262, 200, 42, "Alembic 1.13", "24 个迁移版本", GREEN, GREEN, fs=12.5)
box(550, 262, 200, 42, "asyncmy/aiomysql", "按平台切换驱动", GREEN, GREEN, fs=11.5)
box(768, 262, 116, 42, "MySQL", "远程阿里云", GREEN, GREEN, fs=12.5)
box(72, 312, 812, 28, "cachetools 5.5.0 内存缓存（无 Redis）· 启动 cache_warmer 预热 · /cache-stats 监控", "", GREEN, GREEN, fs=11)

# 4. 认证与安全
container(60, 340, 840, 72, "认证与安全")
box(72, 370, 300, 36, "python-jose (JWT)", "SECRET_KEY · 30天过期", ORANGE, ORANGE, fs=12.5)
box(388, 370, 260, 36, "wechatpy 1.8.18", "微信小程序登录", ORANGE, ORANGE, fs=12.5)
box(664, 370, 220, 36, "deps 注入用户", "admin 路由待加鉴权", ORANGE, ORANGE, fs=12)

# 5. AI 预测编排 (核心特色)
container(60, 424, 840, 110, "AI 预测编排 (核心特色)")
box(72, 454, 300, 42, "LangGraph ≥0.6", "StateGraph 并行预测+retry", PURPLE, PURPLE, fs=13)
box(388, 454, 250, 42, "OfoxAI 网关", "openai 客户端 · 10+ 模型", PURPLE, PURPLE, fs=12.5)
box(652, 454, 232, 42, "DeepSeek 汇总", "aggregate 共识", PURPLE, PURPLE, fs=12.5)
box(72, 506, 812, 18, "ai_predictor · prediction_parsers · prediction_evaluator 配套", "", PURPLE, PURPLE, fs=10)

# 6. 定时调度
container(60, 546, 840, 72, "定时调度 (APScheduler 3.10.4)")
box(72, 576, 812, 36, "00:30 Polymarket · 01:00 生成预测 · 02:00 同步 · */6h 赔率 · 22:00 Telegram", "", RED, RED, fs=11.5)

# 7. 外部集成 & 通知
container(60, 630, 840, 96, "外部集成 &amp; 通知 (httpx 0.27)")
box(72, 660, 250, 42, "Highlightly API", "足球数据源(替 API-Football)", CYAN, CYAN, fs=11.5)
box(336, 660, 250, 42, "Polymarket", "只读 · 经本机代理 10808", CYAN, CYAN, fs=12.5)
box(600, 660, 288, 42, "Telegram", "每日推送 + 分享图", CYAN, CYAN, fs=12.5)
box(336, 710, 250, 18, "Pillow 头像/分享图", "", CYAN, CYAN, fs=10)
box(600, 710, 288, 18, "loguru 全量日志", "", CYAN, CYAN, fs=10)

# 8. 配置 & 工程工具
container(60, 738, 840, 72, "配置 &amp; 工程工具")
box(72, 768, 280, 36, "pydantic-settings", ".env 配置管理", PINK, PINK, fs=12.5)
box(368, 768, 220, 36, "python-dotenv", "读 .env", PINK, PINK, fs=12.5)
box(604, 768, 280, 36, "locust + gevent", "压测 locustfile.py", PINK, PINK, fs=12)

# 9. 前端 / 调用方
add(f'<rect x="60" y="822" width="840" height="60" rx="12" fill="#F1F5F9" '
    f'stroke="{GRAY}" stroke-width="1.5"/>')
add(f'<text x="480" y="850" fill="{TITLE}" font-size="15" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">前端 / 调用方 (Taro 多端 · /api/v1)</text>')
add(f'<text x="480" y="870" fill="{SUB}" font-size="11" text-anchor="middle" '
    f'font-family="{FONT}">dev: 127.0.0.1:8000 · prod: https://marathoninfo.top</text>')

# 竖向连接箭头（居中 x=480，走容器间空白）
varrow(480, 128, 140, BLUE, "路由")
varrow(480, 220, 232, GREEN, "读写")
varrow(480, 328, 340, ORANGE, "鉴权")
varrow(480, 412, 424, PURPLE, "编排")
varrow(480, 534, 546, RED, "调度")
varrow(480, 618, 630, CYAN, "调用")
varrow(480, 726, 738, PINK, "配置")
varrow(480, 810, 822, BLUE, "服务")

add('</svg>')

OUT.write_text("\n".join(L), encoding="utf-8")
print("SVG generated:", OUT)
