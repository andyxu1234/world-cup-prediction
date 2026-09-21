# -*- coding: utf-8 -*-
"""生成 world-cup-prediction 每日预测数据流图 (Style 1 Flat Icon)。"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data-flow.svg"

FONT = "'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', 'SimHei', sans-serif"
BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#16a34a"
PURPLE = "#9333ea"
GRAY = "#6b7280"
ORANGE = "#ea580c"
BOX_STROKE = "#d1d5db"
TXT = "#111827"
SUB = "#6b7280"
CONT_TITLE = "#374151"

L = []


def add(s):
    L.append(s)


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


def rhombus(cx, cy, w, h, label, fill="#fff7ed", stroke="#fed7aa", fs=12):
    add(f'<polygon points="{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    add(f'<text x="{cx}" y="{cy+4}" fill="{TXT}" font-size="{fs}" font-weight="600" '
        f'text-anchor="middle" font-family="{FONT}">{label}</text>')


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


# ---------- canvas ----------
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 760" width="1000" height="760">')
add(f'<style>text{{font-family:{FONT};}}</style>')
add('<defs>'
     f'<marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{BLUE}"/></marker>'
     f'<marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{GRAY}"/></marker>'
     f'<marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{GREEN}"/></marker>'
     f'<marker id="arrow-orange" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="{ORANGE}"/></marker>'
     '</defs>')
add('<rect width="1000" height="760" fill="#ffffff"/>')

add(f'<text x="500" y="34" fill="{TXT}" font-size="20" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">每日比赛预测 · 数据流图</text>')
add(f'<text x="500" y="56" fill="{SUB}" font-size="12" text-anchor="middle" '
    f'font-family="{FONT}">调度触发 → 数据同步 → 赔率快照 → 多模型预测 → 落库 → 推送 / 晨间简报</text>')

# top trigger
box(370, 78, 260, 46, "APScheduler 触发", "01:00 生成当日预测", fill="#eff6ff", stroke="#bfdbfe")

# stage 2 data sync
box(370, 164, 260, 54, "比赛 / 积分榜同步", "match_sync 服务", fill="#ffffff")
add(f'<text x="370" y="200" fill="{SUB}" font-size="11" font-family="{FONT}"></text>')
# external Highlightly (left)
box(70, 170, 200, 44, "Highlightly API", "外部比赛数据源", fill="#f0fdf4", stroke="#bbf7d0")
arrow(270, 191, 370, 191, GRAY, "比赛JSON", dash="5 3", marker="arrow-gray")

# stage 3 odds snapshot
box(370, 254, 260, 54, "赔率快照", "odds_service · 每 6h", fill="#ffffff")
box(70, 260, 200, 44, "博彩公司赔率", "bookmakers / match_odds", fill="#f0fdf4", stroke="#bbf7d0")
arrow(270, 282, 370, 282, GRAY, "赔率快照", dash="5 3", marker="arrow-gray")

# stage 4 LangGraph predict
box(340, 344, 320, 60, "LangGraph 并行预测", "10+ LLM via OfoxAI · 校验+共识", fill="#faf5ff", stroke="#d8b4fe")
box(70, 350, 200, 44, "OfoxAI / LLM 阵", "模型输出 JSON", fill="#faf5ff", stroke="#d8b4fe")
arrow(270, 372, 340, 372, PURPLE, "预测JSON", marker="arrow-blue")

# stage 5 validate + consensus
box(370, 440, 260, 54, "校验 + 共识汇总", "predictions / prediction_summary", fill="#ffffff")

# stage 6 MySQL
box(370, 530, 260, 54, "MySQL 落库", "predictions / odds / standings", fill="#eff6ff", stroke="#bfdbfe")

rsp = [
    # trigger -> sync
    ("arrow", (500, 124, 500, 164), BLUE, "触发"),
    # sync -> odds
    ("arrow", (500, 218, 500, 254), BLUE, ""),
    # odds -> predict
    ("arrow", (500, 308, 500, 344), BLUE, ""),
    # predict -> validate
    ("arrow", (500, 404, 500, 440), BLUE, ""),
    # validate -> mysql
    ("arrow", (500, 494, 500, 530), GREEN, "落库"),
]
for kind, args, color, label in rsp:
    arrow(*args, color=color, label=label if label else None)

# branch outputs from MySQL
# Telegram push (right)
box(720, 520, 220, 54, "Telegram 每日推送", "22:00 · telegram_daily_push", fill="#f0fdf4", stroke="#bbf7d0")
arrow_path([(630, 557), (720, 557)], GRAY, "每日推送", dash="5 3", marker="arrow-gray")
# Morning digest (left)
box(60, 520, 240, 54, "晨间简报 (07:00)", "CodeBuddy 自动化 → predict_engine.py", fill="#fff7ed", stroke="#fed7aa")
arrow_path([(370, 557), (300, 557)], ORANGE, "读库+计算", dash="5 3", marker="arrow-orange")
box(60, 606, 240, 44, "Markdown 简报回显", "三项预测: 胜负平/大小球/比分", fill="#fff7ed", stroke="#fed7aa")
arrow(180, 574, 180, 606, ORANGE, "", marker="arrow-orange")

# frontend query branch (side)
box(720, 434, 220, 44, "前端实时查询", "小程序 / H5 / APK", fill="#eff6ff", stroke="#bfdbfe")
arrow_path([(630, 557), (720, 500), (720, 478)], BLUE, "查询预测", marker="arrow-blue")

# legend
ly0 = 712
add(f'<line x1="70" y1="{ly0}" x2="110" y2="{ly0}" stroke="{BLUE}" stroke-width="1.8" marker-end="url(#arrow-blue)"/>')
add(f'<text x="116" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">主数据流</text>')
add(f'<line x1="230" y1="{ly0}" x2="270" y2="{ly0}" stroke="{GRAY}" stroke-width="1.8" stroke-dasharray="5 3" marker-end="url(#arrow-gray)"/>')
add(f'<text x="276" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">外部同步 / 异步</text>')
add(f'<line x1="430" y1="{ly0}" x2="470" y2="{ly0}" stroke="{GREEN}" stroke-width="1.8" marker-end="url(#arrow-green)"/>')
add(f'<text x="476" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">落库</text>')
add(f'<line x1="560" y1="{ly0}" x2="600" y2="{ly0}" stroke="{ORANGE}" stroke-width="1.8" stroke-dasharray="5 3" marker-end="url(#arrow-orange)"/>')
add(f'<text x="606" y="{ly0+4}" fill="{SUB}" font-size="12" font-family="{FONT}">晨间简报生成</text>')

add('</svg>')

OUT.write_text("\n".join(L), encoding="utf-8")
print("written", OUT, "lines", len(L))
