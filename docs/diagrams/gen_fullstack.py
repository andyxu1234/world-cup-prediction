# -*- coding: utf-8 -*-
"""前后端联动全景图生成器 (Style 1 Flat Icon)
输出 docs/diagrams/fullstack.svg —— 串起 frontend-stack.svg + backend-stack.svg
线型约定:
  蓝实线  = 主请求链路 (前端页面 → Taro.request → /api/v1 → FastAPI → Service → DB)
  紫虚线  = AI 预测编排链路 (FastAPI → LangGraph → OfoxAI → LLM → 落库)
  红虚线  = 定时调度触发 (APScheduler → FastAPI 生成预测)
  灰虚线  = 外部/通知调用 (APScheduler → 外部集成)
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "fullstack.svg"

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


def box(x, y, w, h, title, sub, fill, stroke, fs=13, subfs=10):
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


def varrow(x, y1, y2, color, label, marker="arrow-blue", dash=None):
    add(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{color}" stroke-width="1.8" '
        + (f'stroke-dasharray="{dash}" ' if dash else '')
        + f'marker-end="url(#{marker})"/>')
    if label:
        add(f'<text x="{x + 9}" y="{(y1 + y2)/2 + 4}" fill="{color}" font-size="10.5" '
            f'font-family="{FONT}">{label}</text>')


def harrow(x1, x2, y, color, label, marker="arrow-blue", dash=None):
    add(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="1.8" '
        + (f'stroke-dasharray="{dash}" ' if dash else '')
        + f'marker-end="url(#{marker})"/>')
    if label:
        add(f'<text x="{(x1 + x2)/2}" y="{y - 7}" fill="{color}" font-size="10.5" '
            f'text-anchor="middle" font-family="{FONT}">{label}</text>')


def path_arrow(pts, color, label, marker="arrow-blue", dash=None):
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.8" '
        + (f'stroke-dasharray="{dash}" ' if dash else '')
        + f'marker-end="url(#{marker})"/>')
    if label:
        mx, my = pts[-2]
        add(f'<text x="{mx + 6}" y="{my - 4}" fill="{color}" font-size="10.5" '
            f'font-family="{FONT}">{label}</text>')


# ---- canvas ----
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 1000" font-family="' + FONT + '">')
add(f'<rect x="0" y="0" width="980" height="1000" fill="{BG}"/>')
markers = [("arrow-blue", BLUE), ("arrow-purple", PURPLE), ("arrow-red", RED), ("arrow-gray", GRAY)]
add('<defs>')
for mid, mc in markers:
    add(f'<marker id="{mid}" markerWidth="10" markerHeight="7" refX="8" refY="3.5" '
        f'orient="auto"><path d="M0,0 L10,3.5 L0,7 Z" fill="{mc}"/></marker>')
add('</defs>')
add(f'<text x="490" y="34" fill="{TITLE}" font-size="19" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">前后端联动全景图</text>')
add(f'<text x="490" y="50" fill="{SUB}" font-size="11.5" text-anchor="middle" '
    f'font-family="{FONT}">Taro 多端前端 → /api/v1 网关 → FastAPI 后端分层 → MySQL / AI 编排 / 外部集成</text>')

# ===== 1. 前端区 =====
container(40, 56, 900, 178, "前端 (Taro 4 多端方案)")
mends = [("微信小程序", "主端 weapp", BLUE), ("H5 网页", "独立 Web 版", CYAN),
         ("支付宝", "alipay", GREEN), ("百度", "swan", ORANGE), ("头条", "tt", PINK)]
mw = 162; mg = (860 - 5 * mw) / 4; mx = 52
for i, (t, s, c) in enumerate(mends):
    box(mx + i * (mw + mg), 78, mw, 34, t, s, "#EFF6FF", c, fs=12, subfs=9)
box(52, 124, 245, 38, "Taro 4.1 + React 18", "多端框架 + UI", BLUE, BLUE, fs=12)
box(307, 124, 200, 38, "TypeScript 5.4", "类型系统", PURPLE, PURPLE, fs=12)
box(517, 124, 200, 38, "zustand 4.5", "全局状态容器", ORANGE, ORANGE, fs=12)
box(727, 124, 213, 38, "Sass / @tarojs", "样式 + 组件", PINK, PINK, fs=12)
box(52, 172, 540, 40, "业务页面 / 组件 (15 页面 · zustand 订阅)", "首页/比赛详情/排行/投票/AI预测", "#EFF6FF", BLUE, fs=12.5, subfs=9.5)
box(607, 172, 333, 40, "Taro.request 封装 (api.ts)", "Bearer token · 重试 · 超时", GREEN, GREEN, fs=12.5, subfs=9.5)

# ===== 2. 网关 / 接入 =====
container(40, 250, 900, 96, "接入 / 部署层 (请求边界)")
box(52, 274, 235, 46, "Nginx", "反向代理 · SSL", GRAY, GRAY, fs=13)
box(695, 274, 235, 46, "Docker + uvicorn", "python:3.12 · 8000", GRAY, GRAY, fs=12.5)
add(f'<text x="490" y="303" fill="{BLUE}" font-size="14" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">/api/v1 · HTTPS</text>')

# ===== 3. 后端区 =====
container(40, 362, 900, 560, "后端 (FastAPI 异步服务 · 远程 MySQL)")
# 左列: 安全/缓存
box(52, 388, 245, 48, "JWT 鉴权 (python-jose)", "SECRET_KEY · 30天", ORANGE, ORANGE, fs=11.5)
box(52, 444, 245, 48, "CORS / StaticFiles", "跨域全开 · 头像/赔率", BLUE, BLUE, fs=11.5)
box(52, 500, 245, 48, "cachetools 内存缓存", "cache_warmer 预热", GREEN, GREEN, fs=11.5)
box(52, 556, 245, 48, "deps 注入当前用户", "admin 路由待加鉴权", ORANGE, ORANGE, fs=11)
# 中轴: 主请求链路 (中心 x=490)
box(312, 388, 356, 48, "FastAPI 0.115", "ASGI · 路由聚合", BLUE, BLUE, fs=13.5)
box(312, 444, 356, 48, "Service 层 (22 服务)", "预测/赔率/积分榜/排行", BLUE, BLUE, fs=12)
box(312, 500, 356, 48, "SQLAlchemy 2.0 async", "ORM · asyncmy/aiomysql", GREEN, GREEN, fs=12)
box(312, 556, 356, 48, "MySQL (远程阿里云)", "Alembic 24 迁移 · AI 落库", GREEN, GREEN, fs=12.5)
# 右列: AI 编排
box(684, 388, 240, 48, "LangGraph ≥0.6", "StateGraph 并行+retry", PURPLE, PURPLE, fs=12)
box(684, 444, 240, 72, "OfoxAI 网关", "openai 客户端 · 10+ LLM → predictions 落库", PURPLE, PURPLE, fs=11.5)
box(684, 528, 240, 40, "APScheduler 3.10", "00:30-22:00 管线", RED, RED, fs=11.5)
# 外部集成 (底部横跨)
box(312, 624, 612, 72, "外部集成 &amp; 通知", "Highlightly 数据源 · Polymarket 只读 · Telegram 推送", CYAN, CYAN, fs=11.5)

# ---- 主请求链路: 蓝实线, 前端区底 → 网关空隙 → FastAPI ----
path_arrow([(490, 234), (490, 250), (490, 274), (490, 388)], BLUE, "HTTPS /api/v1")
varrow(490, 436, 444, BLUE, "")
varrow(490, 492, 500, BLUE, "")
varrow(490, 548, 556, BLUE, "")

# AI 预测链路: 紫虚线
harrow(668, 684, 412, PURPLE, "预测请求", marker="arrow-purple", dash="5 3")
varrow(804, 436, 444, PURPLE, "", marker="arrow-purple", dash="5 3")

# 调度触发: 红虚线, APScheduler → 绕行中轴左间隙 → FastAPI
path_arrow([(684, 548), (300, 548), (300, 388), (312, 388)], RED,
           "01:00 生成预测", marker="arrow-red", dash="5 3")

# 外部/通知调用: 灰虚线, APScheduler → 外部集成框
varrow(804, 568, 624, GRAY, "22:00 推送", marker="arrow-gray", dash="5 3")

# ===== 图例 =====
add(f'<rect x="40" y="944" width="900" height="48" rx="12" fill="#FFFFFF" '
    f'stroke="{CONTAINER_STROKE}" stroke-width="1.2"/>')
add(f'<text x="60" y="974" fill="{TITLE}" font-size="12" font-weight="700" font-family="{FONT}">图例</text>')
legend = [(BLUE, "实线", "主请求链路 (前端 → 后端)"),
          (PURPLE, "虚线", "AI 预测编排链路"),
          (RED, "虚线", "定时调度触发"),
          (GRAY, "虚线", "外部 / 通知调用")]
lx = 150
for c, style, txt in legend:
    add(f'<line x1="{lx}" y1="970" x2="{lx + 28}" y2="970" stroke="{c}" stroke-width="2.2" '
        + ('stroke-dasharray="5 3" ' if style == "虚线" else '') + '/>')
    add(f'<text x="{lx + 34}" y="974" fill="{SUB}" font-size="10.5" font-family="{FONT}">{txt}</text>')
    lx += 210

add('</svg>')

OUT.write_text("\n".join(L), encoding="utf-8")
print("SVG generated:", OUT)
