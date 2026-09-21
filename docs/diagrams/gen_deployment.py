# -*- coding: utf-8 -*-
"""生成 world-cup-prediction 部署拓扑图 (Style 1 Flat Icon)。"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "deployment.svg"

FONT = "'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', 'SimHei', sans-serif"
BLUE = "#2563eb"
GRAY = "#6b7280"
GREEN = "#16a34a"
PURPLE = "#9333ea"
BOX_STROKE = "#d1d5db"
TXT = "#111827"
SUB = "#6b7280"
CONT_TITLE = "#374151"

L = []


def add(s):
    L.append(s)


def zone(x, y, w, h, title, subtitle=None):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" ry="12" '
        f'fill="#fafafa" stroke="{BOX_STROKE}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    add(f'<text x="{x+16}" y="{y+22}" fill="{CONT_TITLE}" font-size="14" '
        f'font-weight="600" font-family="{FONT}">{title}</text>')
    if subtitle:
        add(f'<text x="{x+16}" y="{y+40}" fill="{SUB}" font-size="11" '
            f'font-family="{FONT}">{subtitle}</text>')


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


# ---------- canvas ----------
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 720" width="1000" height="720">')
add(f'<style>text{{font-family:{FONT};}}</style>')
add('<defs>'
     f'<marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{BLUE}"/></marker>'
     f'<marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{GRAY}"/></marker>'
     f'<marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{GREEN}"/></marker>'
     '</defs>')
add('<rect width="1000" height="720" fill="#ffffff"/>')

add(f'<text x="500" y="34" fill="{TXT}" font-size="20" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">部署拓扑图 · Network &amp; Deployment</text>')
add(f'<text x="500" y="56" fill="{SUB}" font-size="12" text-anchor="middle" '
    f'font-family="{FONT}">客户端 → 边缘 Nginx → 容器内 FastAPI → 远程 MySQL；外部 API 经 HTTPS / 代理调用</text>')

# ===== 客户端区 =====
zone(60, 80, 540, 92, "客户端区 (Client)")
box(80, 116, 160, 46, "微信小程序", "Taro · 主入口", fill="#eff6ff", stroke="#bfdbfe")
box(255, 116, 160, 46, "H5 Web", "端口 10086", fill="#eff6ff", stroke="#bfdbfe")
box(430, 116, 160, 46, "独立 APK", "WebView 壳", fill="#eff6ff", stroke="#bfdbfe")

# ===== 边缘区 =====
zone(60, 190, 540, 70, "边缘区 (Edge)")
box(80, 216, 500, 38, "Nginx 反向代理 + TLS + 健康检查", fill="#ffffff")

# ===== 内部服务区 =====
zone(60, 280, 540, 112, "内部服务区 (Internal)")
box(80, 310, 500, 70, "Docker 容器", "FastAPI + APScheduler(6 cron) + TTLCache", fill="#ffffff")

# ===== 数据区 =====
zone(60, 412, 540, 112, "数据区 (Data Store)")
box(80, 442, 500, 70, "MySQL 8.0", "阿里云远程实例 · 18 表", fill="#eff6ff", stroke="#bfdbfe")

# ===== 外部依赖区 =====
zone(640, 80, 300, 470, "外部依赖区 (External)")
box(660, 110, 260, 60, "Highlightly API", "比赛 / 积分榜数据", fill="#f0fdf4", stroke="#bbf7d0")
box(660, 200, 260, 60, "Polymarket API", "预测市场 · 本机代理", fill="#f0fdf4", stroke="#bbf7d0")
box(660, 300, 260, 60, "OfoxAI / LLM 阵", "10+ 模型推理", fill="#faf5ff", stroke="#d8b4fe")
box(660, 400, 260, 60, "Telegram", "每日推送通道", fill="#f0fdf4", stroke="#bbf7d0")

# ===== arrows =====
# client -> nginx (consolidated)
arrow_path([(330, 172), (330, 190)], BLUE, "HTTPS/TLS")
# nginx -> docker
arrow_path([(330, 260), (330, 280)], BLUE, "反向代理 :8000")
# docker -> mysql
arrow_path([(330, 392), (330, 412)], GREEN, "SQL 3306")

# docker -> external (orthogonal, gap lanes 580-660); start at Docker right edge x=580
# Highlightly
arrow_path([(580, 330), (620, 330), (620, 140), (640, 140)], GRAY, "GET 比赛", dash="5 3", marker="arrow-gray")
# Polymarket
arrow_path([(580, 345), (600, 345), (600, 230), (640, 230)], GRAY, "GET 市场", dash="5 3", marker="arrow-gray")
# OfoxAI (near-straight)
arrow_path([(580, 360), (640, 330)], PURPLE, "LLM API", marker="arrow-blue")
# Telegram
arrow_path([(580, 375), (660, 430)], GRAY, "推送", dash="5 3", marker="arrow-gray")

# ===== legend =====
ly0 = 672
add(f'<line x1="70" y1="{ly0}" x2="110" y2="{ly0}" stroke="{BLUE}" stroke-width="1.8" marker-end="url(#arrow-blue)"/>')
add(f'<text x="116" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">主链路 (HTTPS / 代理 / SQL)</text>')
add(f'<line x1="350" y1="{ly0}" x2="390" y2="{ly0}" stroke="{GRAY}" stroke-width="1.8" stroke-dasharray="5 3" marker-end="url(#arrow-gray)"/>')
add(f'<text x="396" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">外部 API 同步 (异步)</text>')
add(f'<line x1="640" y1="{ly0}" x2="680" y2="{ly0}" stroke="{PURPLE}" stroke-width="1.8" marker-end="url(#arrow-blue)"/>')
add(f'<text x="686" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">LLM 推理调用</text>')

add('</svg>')

OUT.write_text("\n".join(L), encoding="utf-8")
print("written", OUT, "lines", len(L))
