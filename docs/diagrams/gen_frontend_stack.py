# -*- coding: utf-8 -*-
"""前端技术栈分层图生成器 (Style 1 Flat Icon)
输出 docs/diagrams/frontend-stack.svg
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "frontend-stack.svg"

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


def box(x, y, w, h, title, sub, fill, stroke, fs=14, subfs=10.5):
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
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 770" font-family="' + FONT + '">')
add(f'<rect x="0" y="0" width="960" height="770" fill="{BG}"/>')
add(f'<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="8" refY="3.5" '
    f'orient="auto"><path d="M0,0 L10,3.5 L0,7 Z" fill="{BLUE}"/></marker></defs>')
add(f'<text x="480" y="34" fill="{TITLE}" font-size="19" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">前端技术栈分层图</text>')
add(f'<text x="480" y="50" fill="{SUB}" font-size="11.5" text-anchor="middle" '
    f'font-family="{FONT}">Taro 4 多端方案 · 自上而下 = 产物 → 框架 → 能力层 → 后端对接</text>')

# 1. 多端产物
container(60, 56, 840, 72, "多端产物 (构建目标)")
mends = [("微信小程序", "weapp · 主端", BLUE), ("H5 网页", "独立 Web 版", CYAN),
         ("支付宝", "alipay", GREEN), ("百度", "swan", ORANGE), ("头条", "tt", PINK)]
mw = 148
mx = 72
mg = (816 - 5 * mw) / 4
for i, (t, s, c) in enumerate(mends):
    box(mx + i * (mw + mg), 86, mw, 34, t, s, "#EFF6FF", c, fs=12.5, subfs=9.5)

# 2. 核心框架
container(60, 140, 840, 80, "核心框架与语言")
box(72, 170, 300, 42, "Taro 4.1.11", "React 语法多端框架", BLUE, BLUE, fs=14)
box(388, 170, 200, 42, "React 18.3", "UI 框架", CYAN, CYAN, fs=14)
box(604, 170, 280, 42, "TypeScript 5.4", "类型系统", PURPLE, PURPLE, fs=14)

# 3. 状态管理
container(60, 232, 840, 72, "状态管理")
box(72, 262, 280, 36, "zustand 4.5", "轻量 store · 替代 Redux", ORANGE, ORANGE, fs=13.5)

# 4. 网络层
container(60, 312, 840, 72, "网络层 (自封装 · 无第三方请求库)")
box(72, 342, 380, 36, "Taro.request 封装", "api.ts · token/重试/超时", GREEN, GREEN, fs=12.5)
box(468, 342, 240, 36, "Taro.uploadFile", "头像上传", GREEN, GREEN, fs=12.5)

# 5. UI 与样式
container(60, 392, 840, 72, "UI 与样式")
box(72, 422, 320, 36, "@tarojs/components", "Taro 自带组件 · 无第三方 UI 库", PINK, PINK, fs=12)
box(408, 422, 360, 36, "Sass / SCSS", "全局变量注入 variables.scss", PINK, PINK, fs=12.5)

# 6. 构建与工具链
container(60, 472, 840, 72, "构建与工具链")
bw = 190
bx = 72
bg = (816 - 4 * bw) / 3
for i, (t, s) in enumerate([("webpack5", "Taro 编译器"), ("Babel", "babel-preset-taro"),
                            ("pxtransform", "750 设计稿适配"), ("postcss", "autoprefixer")]):
    box(bx + i * (bw + bg), 502, bw, 36, t, s, "#FEF2F2", RED, fs=12.5, subfs=9.5)

# 7. 存储与路由
container(60, 552, 840, 72, "存储与路由")
box(72, 582, 360, 36, "Taro 本地存储", "getStorageSync 缓存 token/联赛", GRAY, GRAY, fs=12.5)
box(448, 582, 420, 36, "Taro 内置路由", "app.config.ts pages + navigateTo", GRAY, GRAY, fs=12)

# 8. 后端对接
add(f'<rect x="60" y="632" width="840" height="64" rx="12" fill="#F1F5F9" '
    f'stroke="{GRAY}" stroke-width="1.5"/>')
add(f'<text x="480" y="662" fill="{TITLE}" font-size="15" font-weight="700" '
    f'text-anchor="middle" font-family="{FONT}">后端 /api/v1 (FastAPI · 远程 MySQL)</text>')
add(f'<text x="480" y="682" fill="{SUB}" font-size="11" text-anchor="middle" '
    f'font-family="{FONT}">dev: 127.0.0.1:8000 · prod: https://marathoninfo.top</text>')

# 竖向连接箭头（居中 x=480，走容器间空白，不穿透 box）
varrow(480, 128, 140, BLUE, "编译为")
varrow(480, 220, 232, BLUE, "支撑")
varrow(480, 304, 312, BLUE, "调用")
varrow(480, 384, 392, BLUE, "使用")
varrow(480, 464, 472, BLUE, "构建")
varrow(480, 544, 552, BLUE, "依赖")
varrow(480, 624, 632, BLUE, "请求")

add('</svg>')

OUT.write_text("\n".join(L), encoding="utf-8")
print("SVG generated:", OUT)
