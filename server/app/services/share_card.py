"""分享卡片生成服务"""

from __future__ import annotations

import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.match import Match
from app.models.prediction import Prediction
from app.models.ai_model import AIModel


async def get_share_card_data(db: AsyncSession, match_id: int) -> dict:
    """获取分享卡片数据"""
    stmt = (
        select(Match)
        .where(Match.id == match_id)
        .options(
            selectinload(Match.home_team), selectinload(Match.away_team),
            selectinload(Match.predictions).selectinload(Prediction.ai_model),
        )
    )
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()
    if not match:
        raise ValueError(f"Match {match_id} not found")

    predictions = []
    for pred in match.predictions:
        predictions.append({
            "model_name": pred.ai_model.name,
            "model_avatar": pred.ai_model.avatar_url,
            "result": pred.result,
            "score_home": pred.score_home,
            "score_away": pred.score_away,
            "confidence": pred.confidence,
        })

    return {
        "match_id": match.id,
        "home_team": match.home_team.cn_name or match.home_team.name,
        "home_flag": match.home_team.flag_url,
        "away_team": match.away_team.cn_name or match.away_team.name,
        "away_flag": match.away_team.flag_url,
        "match_time": match.match_time.isoformat() if match.match_time else None,
        "round": match.round,
        "status": match.status,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "predictions": predictions,
    }


def generate_share_card_image(data: dict) -> bytes:
    """用 Pillow 生成分享卡片图片（比赛预测卡），返回 PNG 字节流
    
    设计风格：体育杂志封面级 — 大胆排版、强烈对比、专业感
    布局：绿色品牌顶栏 → 超大对战英雄区 → AI预测卡片区 → 底部信息+二维码
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 750, 1100

    # ===== 配色方案 =====
    GREEN_DARK = (10, 60, 35)        # 深绿（顶栏）
    GREEN_MAIN = (16, 145, 97)       # 主题绿
    GREEN_LIGHT = (232, 250, 243)    # 淡绿背景
    BG = (255, 255, 255)             # 纯白
    TEXT_DARK = (25, 25, 28)         # 主文字
    TEXT_MID = (80, 85, 95)          # 中等灰文字
    TEXT_LIGHT = (160, 165, 175)     # 浅灰文字
    GOLD = (218, 165, 32)            # 金色点缀
    CARD_BG = (248, 250, 252)        # 卡片背景

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ===== 字体加载（加大加粗确保清晰）=====
    try:
        f_hero = ImageFont.truetype("msyh.ttc", 96)      # 队名超大字（核心视觉）
        f_vs = ImageFont.truetype("msyh.ttc", 56)         # VS 徽章
        f_head = ImageFont.truetype("msyh.ttc", 32)       # 顶栏/标题
        f_body = ImageFont.truetype("msyh.ttc", 30)       # 正文
        f_sub = ImageFont.truetype("msyh.ttc", 26)        # 辅助文字
        f_small = ImageFont.truetype("msyh.ttc", 22)      # 小字
        f_micro = ImageFont.truetype("msyh.ttc", 18)      # 微小字
        f_pred_name = ImageFont.truetype("msyh.ttc", 28)   # AI模型名
        f_pred_result = ImageFont.truetype("msyh.ttc", 30) # 预测结果（加粗）
    except (OSError, IOError):
        f_hero = f_vs = f_head = f_body = f_sub = f_small = f_micro = f_pred_name = f_pred_result = ImageFont.load_default()

    # ===== 数据准备 =====
    home = data.get("home_team", "主队")
    away = data.get("away_team", "客队")
    round_text = data.get("round", "")
    match_time = data.get("match_time", "")
    predictions = data.get("predictions", [])

    if match_time:
        try:
            from datetime import datetime, timedelta, timezone
            utc_dt = datetime.fromisoformat(match_time)
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            bj_dt = utc_dt + timedelta(hours=8)
            date_str = bj_dt.strftime("%m月%d日")
            time_str = bj_dt.strftime("%H:%M")
            weekday_map = ["周一","周二","周三","周四","周五","周六","周日"]
            wday_str = weekday_map[bj_dt.weekday()]
        except (ValueError, TypeError):
            date_str = match_time[:10].replace("-", "月") + "日"
            time_str = ""
            wday_str = ""
    else:
        date_str = "待定"
        time_str = ""
        wday_str = ""

    round_cn_map = {
        "Group Stage - 1": "小组赛 第1轮", "Group Stage - 2": "小组赛 第2轮",
        "Group Stage - 3": "小组赛 第3轮", "Round of 32": "三十二强",
        "Round of 16": "十六强", "Quarter-finals": "1/4决赛",
        "Semi-finals": "半决赛", "3rd Place Final": "季军赛", "Final": "决赛",
    }
    round_display = round_cn_map.get(round_text, round_text)

    # ============================================================
    #  ① 顶部绿色品牌栏（全宽深绿条）
    # ============================================================
    bar_h = 90
    draw.rectangle([(0, 0), (W, bar_h)], fill=GREEN_DARK)
    # 左侧足球图标 + 标题
    draw.text((50, bar_h // 2), "\u26bd  2026 FIFA World Cup", fill=(255, 255, 255), font=f_head, anchor="lm")
    # 右侧金色标签
    draw.text((W - 50, bar_h // 2), "AI PREDICTION", fill=GOLD, font=f_small, anchor="rm")

    # ============================================================
    #  ② 英雄对战区（超大字号，视觉冲击）
    # ============================================================
    hero_top = bar_h + 40
    hero_center_y = hero_top + 100

    # --- 主队名 ---
    home_bbox = draw.textbbox((0, 0), home, font=f_hero)
    home_w = home_bbox[2] - home_bbox[0]
    draw.text((W // 2, hero_center_y - 20), home,
              fill=TEXT_DARK, font=f_hero, anchor="mm")

    # --- VS 徽章（醒目的圆角矩形徽章）---
    vs_badge_w = 90
    vs_badge_h = 50
    vs_cx = W // 2
    vs_cy = hero_center_y + 75
    draw.rounded_rectangle(
        [(vs_cx - vs_badge_w // 2, vs_cy - vs_badge_h // 2),
         (vs_cx + vs_badge_w // 2, vs_cy + vs_badge_h // 2)],
        radius=25, fill=GREEN_MAIN
    )
    draw.text((vs_cx, vs_cy + 1), "VS", fill=(255, 255, 255), font=f_vs, anchor="mm")

    # --- 客队名 ---
    away_y = vs_cy + 55
    draw.text((W // 2, away_y + 45), away,
              fill=TEXT_DARK, font=f_hero, anchor="mm")

    # ============================================================
    #  ③ AI 预测卡片区（白色圆角卡片，内含列表）
    # ============================================================
    card_top = away_y + 110
    card_margin = 36
    card_inner_pad = 32

    # 卡片背景
    draw.rounded_rectangle(
        [(card_margin, card_top), (W - card_margin, card_top + 320)],
        radius=20, fill=CARD_BG, outline=(230, 233, 240), width=1
    )

    # 卡片标题行
    title_x = card_margin + card_inner_pad
    title_y = card_top + 28
    # 绿色小竖条装饰
    draw.rectangle([(title_x, title_y), (title_x + 5, title_y + 26)], fill=GREEN_MAIN)
    draw.text((title_x + 16, title_y + 13), "AI 模型预测",
              fill=TEXT_DARK, font=f_body, anchor="lm")

    # 预测列表
    result_map = {"home_win": "主胜", "draw": "平局", "away_win": "客胜"}
    result_colors = {"home_win": GREEN_MAIN, "draw": (200, 150, 30), "away_win": (59, 130, 246)}

    item_start_y = title_y + 54
    row_h = 58

    for i, p in enumerate(predictions[:4]):
        iy = item_start_y + i * row_h
        name = p.get("model_name", "AI")
        res = p.get("result", "")
        res_label = result_map.get(res, "?")
        sh = p.get("score_home", "")
        sa = p.get("score_away", "")
        score_str = f" {sh}:{sa}" if str(sh) and str(sa) else ""
        conf = p.get("confidence", 0)

        # 模型名
        draw.text((title_x, iy + 18), name, fill=TEXT_DARK, font=f_pred_name, anchor="lm")

        # 预测结果（带颜色）
        res_color = result_colors.get(res, TEXT_MID)
        res_text = res_label + score_str
        res_x = title_x + 180
        draw.text((res_x, iy + 19), res_text, fill=res_color, font=f_pred_result, anchor="lm")

        # 信心进度条
        bar_x = res_x + 140
        bar_w = 130
        bar_h_val = 16
        bar_r = 8
        bar_cy = iy + 19
        # 背景
        draw.rounded_rectangle(
            [(bar_x, bar_cy - bar_h_val // 2), (bar_x + bar_w, bar_cy + bar_h_val // 2)],
            radius=bar_r, fill=(235, 238, 245)
        )
        # 填充
        fill_w = max(8, int(bar_w * (conf / 10))) if conf else 0
        if fill_w > 0:
            draw.rounded_rectangle(
                [(bar_x, bar_cy - bar_h_val // 2), (bar_x + fill_w, bar_cy + bar_h_val // 2)],
                radius=bar_r, fill=GREEN_MAIN
            )
        # 百分比数字
        pct_text = f"{conf:.0f}%" if conf else "-"
        draw.text((bar_x + bar_w + 12, bar_cy), pct_text, fill=TEXT_LIGHT, font=f_sub, anchor="lm")

    # ============================================================
    #  ④ 底部信息区 — 赛事详情 + 小程序码
    # ============================================================
    bottom_top = card_top + 340

    # 分割线
    draw.line([(card_margin, bottom_top), (W - card_margin, bottom_top)], fill=(230, 233, 240), width=1)

    info_y = bottom_top + 28

    # ---- 左侧：赛事信息 ----
    left_x = card_margin

    # 轮次标签（绿色胶囊）
    rd_bbox = draw.textbbox((0, 0), round_display, font=f_small)
    rd_w = rd_bbox[2] - rd_bbox[0] + 32
    rd_h = 40
    rd_r = 20
    draw.rounded_rectangle(
        [(left_x, info_y), (left_x + rd_w, info_y + rd_h)],
        radius=rd_r, fill=GREEN_LIGHT
    )
    draw.text((left_x + rd_w // 2, info_y + rd_h // 2),
              round_display, fill=GREEN_MAIN, font=f_small, anchor="mm")

    # 日期时间
    dt_y = info_y + rd_h + 18
    dt_parts = [date_str]
    if wday_str:
        dt_parts.append(wday_str)
    if time_str:
        dt_parts.append(time_str)
    draw.text((left_x, dt_y), "  ".join(dt_parts), fill=TEXT_MID, font=f_body, anchor="lt")

    # 对阵简写
    match_y = dt_y + 42
    draw.text((left_x, match_y), f"{home}  \u224f  {away}", fill=TEXT_DARK, font=f_sub, anchor="lt")

    # ---- 右侧：小程序码 ----
    import os
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qr_img_path = os.path.join(_base_dir, "docs", "mini.jpg")

    qr_size = 170
    qr_right = card_margin
    qr_x = W - qr_right - qr_size
    qr_y = info_y - 6

    qr_loaded = False
    try:
        if os.path.exists(qr_img_path):
            qr_img = Image.open(qr_img_path).convert("RGBA")
            qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
            img.paste(qr_img, (qr_x, qr_y), qr_img if qr_img.mode == "RGBA" else None)
            draw = ImageDraw.Draw(img)
            qr_loaded = True
    except Exception as e:
        pass  # 下面画占位

    if not qr_loaded:
        # 占位框（带虚线边框效果）
        draw.rounded_rectangle(
            [(qr_x, qr_y), (qr_x + qr_size, qr_y + qr_size)],
            radius=14, outline=(210, 215, 225), width=2, fill=(248, 250, 252)
        )
        draw.text((qr_x + qr_size // 2, qr_y + qr_size // 2 - 10),
                  "小程序码", fill=TEXT_LIGHT, font=f_small, anchor="mm")
        draw.text((qr_x + qr_size // 2, qr_y + qr_size // 2 + 20),
                  "QR Code", fill=TEXT_LIGHT, font=f_micro, anchor="mm")

    # 二维码下方提示
    hint_y = qr_y + qr_size + 14
    draw.text((qr_x + qr_size // 2, hint_y), "长按识别", fill=TEXT_LIGHT, font=f_micro, anchor="mm")
    draw.text((qr_x + qr_size // 2, hint_y + 22), "进入小程序", fill=TEXT_LIGHT, font=f_micro, anchor="mm")

    # ============================================================
    #  ⑤ 底部品牌 footer
    # ============================================================
    footer_y = H - 46
    draw.text((W // 2, footer_y),
              "AI \u9884\u6d4b\u4e16\u754c\u676a  \u00b7  Powered by Multi-AI",
              fill=(200, 205, 212), font=f_micro, anchor="mm")

    # 输出 PNG
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    return buffer.getvalue()


def generate_invite_card_image(data: dict) -> bytes:
    """用 Pillow 生成邀请卡图片（个人中心邀请好友），返回 PNG 字节流"""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import urllib.request
    import os
    import tempfile

    W, H = 750, 1000  # 竖版卡片

    # 配色：深绿渐变主题（与小程序整体风格一致）
    BG_TOP = (13, 40, 24)
    BG_BOTTOM = (26, 77, 46)
    CARD_BG = (255, 255, 255)
    TEXT_DARK = (30, 41, 59)
    TEXT_WHITE = (255, 255, 255)
    TEXT_GOLD = (251, 191, 36)
    ACCENT_GREEN = (16, 185, 129)
    ACCENT_PURPLE = (168, 85, 247)
    GRAY_LIGHT = (148, 163, 184)
    STAT_CARD_BG = (248, 250, 252)

    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # 绘制渐变背景
    for y in range(H):
        ratio = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # 重新获取 draw 对象（因为上面画了很多线）
    draw = ImageDraw.Draw(img)

    # 加载字体
    try:
        font_xl = ImageFont.truetype("msyh.ttc", 44)
        font_lg = ImageFont.truetype("msyh.ttc", 32)
        font_md = ImageFont.truetype("msyh.ttc", 26)
        font_sm = ImageFont.truetype("msyh.ttc", 20)
        font_xs = ImageFont.truetype("msyh.ttc", 16)
        font_num = ImageFont.truetype("msyh.ttc", 52)
        font_num_sm = ImageFont.truetype("msyh.ttc", 28)
    except (OSError, IOError):
        font_xl = font_lg = font_md = font_sm = font_xs = font_num = font_num_sm = ImageFont.load_default()

    nickname = data.get("nickname", "预言家")
    avatar_url = data.get("avatar_url", "")
    total_votes = data.get("total_votes", 0)
    correct_results = data.get("correct_results", 0)
    correct_scores = data.get("correct_scores", 0)
    ai_ranking = data.get("ai_ranking", [])

    # ======== 顶部品牌区 ========
    draw.text((W // 2, 60), "🏆  AI 预测世界杯", fill=TEXT_GOLD, font=font_md, anchor="mm")
    draw.text((W // 2, 100), "—— 谁才是最强预言家？ ——", fill=GRAY_LIGHT, font=font_xs, anchor="mm")

    # ======== 用户头像+昵称区 ========
    avatar_center_y = 200
    avatar_size = 120

    # 头像圆形外框
    avatar_left = W // 2 - avatar_size // 2
    avatar_top = avatar_center_y - avatar_size // 2
    draw.ellipse(
        [(avatar_left - 6, avatar_top - 6), (avatar_left + avatar_size + 6, avatar_top + avatar_size + 6)],
        outline=TEXT_GOLD, width=3
    )
    draw.ellipse(
        [(avatar_left, avatar_top), (avatar_left + avatar_size, avatar_top + avatar_size)],
        fill=(80, 120, 90),
    )

    # 尝试加载头像图片
    try:
        if avatar_url and avatar_url.startswith("http"):
            req = urllib.request.Request(avatar_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                avatar_img = Image.open(io.BytesIO(resp.read())).convert("RGBA")
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.LANCZOS)
                # 创建圆形蒙版
                mask = Image.new("L", (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([(0, 0), (avatar_size, avatar_size)], fill=255)
                # 粘贴带蒙版的头像
                img.paste(avatar_img, (avatar_left, avatar_top), mask)
                draw = ImageDraw.Draw(img)
        elif avatar_url and os.path.exists(avatar_url):
            avatar_img = Image.open(avatar_url).convert("RGBA")
            avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.LANCZOS)
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([(0, 0), (avatar_size, avatar_size)], fill=255)
            img.paste(avatar_img, (avatar_left, avatar_top), mask)
            draw = ImageDraw.Draw(img)
    except Exception:
        pass  # 使用默认背景色即可

    # 昵称
    draw.text((W // 2, 285), nickname, fill=TEXT_WHITE, font=font_lg, anchor="mm")
    draw.text((W // 2, 320), "邀你挑战 AI 预测！", fill=ACCENT_GREEN, font=font_md, anchor="mm")

    # ======== 战绩卡片 ========
    card_top = 360
    card_h = 130
    card_margin = 32
    draw.rounded_rectangle(
        [(card_margin, card_top), (W - card_margin, card_top + card_h)],
        radius=16, fill=STAT_CARD_BG
    )
    draw.text((W // 2, card_top + 28), "我的战绩", fill=GRAY_LIGHT, font=font_xs, anchor="mm")

    # 三列数据
    col_w = (W - card_margin * 2) // 3
    stats = [
        ("已投票", str(total_votes)),
        ("胜负正确", str(correct_results)),
        ("比分命中", str(correct_scores)),
    ]
    for i, (label, val) in enumerate(stats):
        cx = card_margin + col_w * i + col_w // 2
        cy = card_top + card_h - 35
        draw.text((cx, cy - 18), val, fill=ACCENT_GREEN, font=font_num_sm, anchor="mm")
        draw.text((cx, cy + 14), label, fill=GRAY_LIGHT, font=font_xs, anchor="mm")

    # ======== AI 排行榜 teaser ========
    ai_top = card_top + card_h + 28
    # 标题
    draw.text((W // 2, ai_top + 12), "🤖  AI 先知排行榜 TOP3", fill=TEXT_WHITE, font=font_sm, anchor="mm")

    ai_list_top = ai_top + 38
    row_h = 56
    rank_colors = [
        (255, 215, 0),    # 金
        (192, 192, 192),  # 银
        (205, 127, 50),   # 铜
    ]

    for i, ai in enumerate(ai_ranking[:3]):
        ry = ai_list_top + i * row_h
        name = ai.get("name", f"AI-{i+1}")
        score = ai.get("result_accuracy", 0)
        acc_str = f"{score:.1f}%" if isinstance(score, (int, float)) else str(score)

        # 排名圆圈
        r_cx = 70
        r_r = 14
        draw.ellipse([(r_cx - r_r, ry - r_r + 10), (r_cx + r_r, ry + r_r + 10)], fill=rank_colors[i])
        draw.text((r_cx, ry + 18), str(i + 1), fill=TEXT_DARK, font=font_xs, anchor="mm")

        # 名字
        draw.text((105, ry + 18), name, fill=TEXT_WHITE, font=font_sm, anchor="lm")
        # 分数
        draw.text((W - 65, ry + 18), acc_str, fill=TEXT_GOLD, font=font_sm, anchor="rm")

    # ======== CTA 按钮 ========
    cta_top = ai_list_top + 3 * row_h + 32
    cta_h = 72
    cta_margin = 60
    draw.rounded_rectangle(
        [(cta_margin, cta_top), (W - cta_margin, cta_top + cta_h)],
        radius=36, fill=ACCENT_GREEN
    )
    draw.text((W // 2, cta_top + cta_h // 2), "你的预言能打败 AI ？", fill=TEXT_WHITE, font=font_md, anchor="mm")
    draw.text((W // 2, cta_top + cta_h // 2 + 24), "立即加入挑战 →", fill=TEXT_WHITE, font=font_xs, anchor="mm")

    # ======== 底部区域 ========
    btm_top = H - 160
    # 分割虚线效果
    dash_gap = 8
    dx = card_margin
    while dx < W - card_margin:
        draw.line([(dx, btm_top - 20), (min(dx + dash_gap, W - card_margin), btm_top - 20)],
                  fill=(60, 100, 70), width=1)
        dx += dash_gap * 2

    # 小程序码占位框
    qr_size = 96
    qr_left = W // 2 - qr_size // 2
    draw.rounded_rectangle(
        [(qr_left, btm_top), (qr_left + qr_size, btm_top + qr_size)],
        radius=12, fill=CARD_BG
    )
    draw.text((qr_left + qr_size // 2, btm_top + qr_size // 2), "小程序码",
              fill=GRAY_LIGHT, font=font_xs, anchor="mm")

    draw.text((W // 2, btm_top + qr_size + 18), "扫码加入预言家行列",
              fill=GRAY_LIGHT, font=font_xs, anchor="mm")

    # 输出 PNG
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    return buffer.getvalue()
