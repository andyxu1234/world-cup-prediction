# -*- coding: utf-8 -*-
"""生成 world-cup-prediction 系统架构图 (Style 1 Flat Icon)。

布局：客户端 → 接入 → 后端(FastAPI) → AI 编排(LangGraph+OfoxAI+LLM) → MySQL(底部居中)；
外部依赖(Highlightly/Polymarket/LLM云服务/Telegram) 置于右侧列，由后端/AI 水平接入，
避免箭头穿透 AI 层。
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "architecture.svg"

FONT = "'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', 'SimHei', sans-serif"
BLUE = "#2563eb"
GREEN = "#16a34a"
GRAY = "#6b7280"
PURPLE = "#9333ea"
BOX_STROKE = "#d1d5db"
TXT = "#111827"
SUB = "#6b7280"
CONT_TITLE = "#374151"

L = []


def add(s):
    L.append(s)


def container(x, y, w, h, title):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" ry="12" '
        f'fill="#fafafa" stroke="{BOX_STROKE}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    add(f'<text x="{x+16}" y="{y+22}" fill="{CONT_TITLE}" font-size="14" '
        f'font-weight="600" font-family="{FONT}">{title}</text>')


def box(x, y, w, h, label, sub=None, fill="#ffffff", stroke=BOX_STROKE,
        fc=TXT, fs=14, subfs=11):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" ry="8" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    ty = y + h / 2 + (4 if sub else 0)
    add(f'<text x="{x + w/2}" y="{ty}" fill="{fc}" font-size="{fs}" '
        f'font-weight="600" text-anchor="middle" font-family="{FONT}">{label}</text>')
    if sub:
        add(f'<text x="{x + w/2}" y="{y + h - 12}" fill="{SUB}" font-size="{subfs}" '
            f'text-anchor="middle" font-family="{FONT}">{sub}</text>')


def arrow(x1, y1, x2, y2, color=BLUE, label=None, dash=None, lx=None, ly=None,
          marker="arrow-blue"):
    style = f'stroke="{color}" stroke-width="1.8" fill="none"'
    if dash:
        style += f' stroke-dasharray="{dash}"'
    add(f'<path d="M {x1},{y1} L {x2},{y2}" {style} marker-end="url(#{marker})"/>')
    if label:
        if lx is None:
            lx = (x1 + x2) / 2
        if ly is None:
            ly = (y1 + y2) / 2 - 6
        add(f'<text x="{lx}" y="{ly}" fill="{color}" font-size="11" '
            f'text-anchor="middle" font-family="{FONT}">{label}</text>')


def arrow_path(pts, color=BLUE, label=None, dash=None, lx=None, ly=None,
               marker="arrow-blue"):
    style = f'stroke="{color}" stroke-width="1.8" fill="none"'
    if dash:
        style += f' stroke-dasharray="{dash}"'
    d = "M " + " L ".join(f"{p[0]},{p[1]}" for p in pts)
    add(f'<path d="{d}" {style} marker-end="url(#{marker})"/>')
    if label:
        if lx is None or ly is None:
            lx, ly = pts[-2][0], pts[-2][1] - 6
        add(f'<text x="{lx}" y="{ly}" fill="{color}" font-size="11" '
            f'text-anchor="middle" font-family="{FONT}">{label}</text>')


def cylinder(cx, top_y, w, h, label, sub=None):
    rx = w / 2
    ry = 14
    bottom = top_y + h
    add(f'<path d="M {cx-rx},{top_y} V {bottom-ry} A {rx},{ry} 0 0 0 {cx+rx},{bottom-ry} V {top_y} Z" '
        f'fill="#eff6ff" stroke="#bfdbfe" stroke-width="1.5"/>')
    add(f'<ellipse cx="{cx}" cy="{top_y}" rx="{rx}" ry="{ry}" '
        f'fill="#dbeafe" stroke="#bfdbfe" stroke-width="1.5"/>')
    add(f'<text x="{cx}" y="{top_y + h/2 - 6}" fill="{TXT}" font-size="14" '
        f'font-weight="600" text-anchor="middle" font-family="{FONT}">{label}</text>')
    if sub:
        add(f'<text x="{cx}" y="{bottom - 12}" fill="{SUB}" font-size="11" '
            f'text-anchor="middle" font-family="{FONT}">{sub}</text>')


# ---------- canvas ----------
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 780" width="1000" height="780">')
add(f'<style>text{{font-family:{FONT};}}</style>')
add('<defs>'
     f'<marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{BLUE}"/></marker>'
     f'<marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{GRAY}"/></marker>'
     f'<marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{GREEN}"/></marker>'
     '</defs>')
add('<rect width="1000" height="780" fill="#ffffff"/>')

add(f'<text x="500" y="34" fill="{TXT}" font-size="20" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">World Cup Prediction · 系统架构图</text>')
add(f'<text x="500" y="56" fill="{SUB}" font-size="12" text-anchor="middle" '
    f'font-family="{FONT}">Taro 跨端前端 · FastAPI 异步后端 · LangGraph 多模型编排 · 远程 MySQL</text>')

# ===== Clients band =====
container(60, 80, 880, 92, "客户端层 (Client)")
box(100, 116, 250, 46, "微信小程序", "Taro · 主入口", fill="#eff6ff", stroke="#bfdbfe")
box(375, 116, 250, 46, "H5 Web", "Taro build:h5 · 端口 10086", fill="#eff6ff", stroke="#bfdbfe")
box(650, 116, 250, 46, "独立 APK", "WebView 壳 · 去微信化", fill="#eff6ff", stroke="#bfdbfe")

# ===== Nginx =====
box(100, 200, 400, 40, "Nginx 反向代理 + HTTPS + 健康检查", fill="#ffffff")

# ===== Backend band =====
container(60, 270, 620, 120, "后端服务层 (FastAPI)")
box(80, 302, 140, 60, "API 路由", "50+ 端点")
box(230, 302, 140, 60, "鉴权", "JWT + 微信")
box(380, 302, 140, 60, "缓存", "TTLCache")
box(530, 302, 140, 60, "调度", "APScheduler·6 cron")

# ===== AI band =====
container(60, 410, 620, 120, "AI 编排层 (LangGraph)")
box(80, 444, 300, 72, "LangGraph 状态图", "并行预测→校验→重试→共识", fill="#faf5ff", stroke="#d8b4fe")
box(395, 444, 140, 72, "OfoxAI 网关", "api.ofox.io", fill="#faf5ff", stroke="#d8b4fe")
box(550, 444, 120, 72, "LLM 模型阵", "DeepSeek等10+", fill="#faf5ff", stroke="#d8b4fe")

# ===== External column =====
container(720, 190, 220, 470, "外部依赖 (External)")
box(740, 214, 180, 80, "Highlightly API", "比赛 / 积分榜数据", fill="#f0fdf4", stroke="#bbf7d0")
box(740, 310, 180, 80, "Polymarket API", "预测市场 · 本机代理", fill="#f0fdf4", stroke="#bbf7d0")
box(740, 406, 180, 80, "LLM 云服务", "DeepSeek/Claude/GPT…", fill="#faf5ff", stroke="#d8b4fe")
box(740, 502, 180, 80, "Telegram", "每日推送 22:00", fill="#f0fdf4", stroke="#bbf7d0")

# ===== Data layer (MySQL) =====
container(60, 560, 620, 140, "数据层 (Data Store)")
cylinder(370, 592, 200, 92, "MySQL 8.0", "远程阿里云 · 18 表")

# ===== arrows =====
# client -> nginx -> backend -> AI (primary vertical, left of center x=300)
arrow(300, 172, 300, 200, BLUE, "HTTPS")
arrow(300, 240, 300, 270, BLUE, "反向代理")
arrow(300, 390, 300, 410, BLUE, "预测请求")
# AI -> MySQL (down into data layer)
arrow(370, 530, 370, 574, GREEN, "读写 预测/赔率/统计")

# backend -> external (horizontal, no gutter where aligned)
arrow(670, 350, 740, 350, GRAY, "00:30 同步", dash="5 3", marker="arrow-gray")   # Scheduler -> Polymarket
arrow(670, 480, 740, 446, PURPLE, "LLM API", marker="arrow-blue")                # AI -> LLM服务
# Highlightly: backend top-right -> gutter x=700 -> external left
arrow_path([(680, 300), (700, 300), (700, 254), (740, 254)], GRAY, "比赛数据",
            dash="5 3", marker="arrow-gray")
# Telegram: Scheduler -> gutter x=700 -> external left
arrow_path([(670, 332), (700, 332), (700, 542), (740, 542)], GRAY, "22:00 推送",
            dash="5 3", marker="arrow-gray")

# ===== legend =====
ly0 = 736
add(f'<line x1="80" y1="{ly0}" x2="120" y2="{ly0}" stroke="{BLUE}" stroke-width="1.8" marker-end="url(#arrow-blue)"/>')
add(f'<text x="126" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">主请求流 (HTTPS / API)</text>')
add(f'<line x1="360" y1="{ly0}" x2="400" y2="{ly0}" stroke="{GRAY}" stroke-width="1.8" stroke-dasharray="5 3" marker-end="url(#arrow-gray)"/>')
add(f'<text x="406" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">异步 / 调度 / 外部同步</text>')
add(f'<line x1="640" y1="{ly0}" x2="680" y2="{ly0}" stroke="{GREEN}" stroke-width="1.8" marker-end="url(#arrow-green)"/>')
add(f'<text x="686" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">数据读写 (MySQL)</text>')

add('</svg>')

OUT.write_text("\n".join(L), encoding="utf-8")
print("written", OUT, "lines", len(L))
