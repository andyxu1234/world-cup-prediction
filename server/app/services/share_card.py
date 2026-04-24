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
    """用 Pillow 生成分享卡片图片（比赛对战卡），返回 PNG 字节流"""
    from PIL import Image, ImageDraw, ImageFont

    # 画布尺寸（微信分享卡片推荐 750x1334 或 900x600）
    W, H = 750, 600
    BG_COLOR = (20, 30, 55)        # 深蓝背景
    TEXT_WHITE = (255, 255, 255)
    TEXT_GOLD = (255, 215, 0)
    TEXT_GRAY = (180, 180, 180)
    ACCENT = (56, 132, 255)         # 蓝色强调

    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 加载字体（使用 Pillow 默认字体，跨平台安全）
    try:
        font_title = ImageFont.truetype("msyh.ttc", 32)      # 微软雅黑
        font_body = ImageFont.truetype("msyh.ttc", 22)
        font_small = ImageFont.truetype("msyh.ttc", 18)
        font_score = ImageFont.truetype("msyh.ttc", 48)
    except (OSError, IOError):
        try:
            font_title = ImageFont.truetype("Arial.ttf", 32)
            font_body = ImageFont.truetype("Arial.ttf", 22)
            font_small = ImageFont.truetype("Arial.ttf", 18)
            font_score = ImageFont.truetype("Arial.ttf", 48)
        except (OSError, IOError):
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_score = ImageFont.load_default()

    # --- 顶部标题栏 ---
    draw.rounded_rectangle([(20, 20), (W - 20, 70)], radius=12, fill=(30, 45, 75))
    draw.text((W // 2, 45), "⚽ 世界杯 AI 预测大赛", fill=TEXT_GOLD, font=font_title, anchor="mm")

    # --- 轮次信息 ---
    round_text = data.get("round", "")
    match_time = data.get("match_time", "")
    if match_time:
        # UTC时间转为北京时间（+8小时）
        try:
            from datetime import datetime, timedelta, timezone
            utc_dt = datetime.fromisoformat(match_time)
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            bj_dt = utc_dt + timedelta(hours=8)
            match_time = bj_dt.strftime("%m月%d日 %H:%M")
        except (ValueError, TypeError):
            match_time = match_time[:16].replace("T", " ")
    draw.text((W // 2, 95), f"{round_text}  |  {match_time}", fill=TEXT_GRAY, font=font_small, anchor="mt")

    # --- VS 区域 ---
    home = data.get("home_team", "???")
    away = data.get("away_team", "???")
    home_score = data.get("home_score")
    away_score = data.get("away_score")

    # 主队名
    draw.text((W // 4, 160), home, fill=TEXT_WHITE, font=font_title, anchor="mt")
    # 客队名
    draw.text((3 * W // 4, 160), away, fill=TEXT_WHITE, font=font_title, anchor="mt")

    # VS / 比分
    if home_score is not None and away_score is not None:
        score_text = f"{home_score}  :  {away_score}"
        draw.text((W // 2, 220), score_text, fill=TEXT_GOLD, font=font_score, anchor="mm")
    else:
        draw.text((W // 2, 220), "VS", fill=ACCENT, font=font_score, anchor="mm")

    # --- 分割线 ---
    draw.line([(40, 280), (W - 40, 280)], fill=(60, 80, 120), width=2)

    # --- AI 预测区域 ---
    draw.text((40, 295), "AI 预测", fill=TEXT_GOLD, font=font_body)

    predictions = data.get("predictions", [])
    y = 330
    if not predictions:
        draw.text((40, y), "暂无 AI 预测", fill=TEXT_GRAY, font=font_body)
    else:
        # 最多显示 5 个预测
        for i, pred in enumerate(predictions[:5]):
            name = pred.get("model_name", "AI")
            result_map = {"home_win": "主胜", "draw": "平局", "away_win": "客胜"}
            result_text = result_map.get(pred.get("result", ""), pred.get("result", ""))
            confidence = pred.get("confidence")
            score_h = pred.get("score_home", "")
            score_a = pred.get("score_away", "")

            # 模型名
            draw.text((50, y), name, fill=TEXT_WHITE, font=font_small)
            # 预测结果
            pred_text = f"{result_text}"
            if score_h != "" and score_a != "":
                pred_text += f"  {score_h}:{score_a}"
            if confidence is not None:
                pred_text += f"  信心 {confidence}%"
            draw.text((250, y), pred_text, fill=ACCENT, font=font_small)

            y += 30

    # --- 底部 ---
    draw.rounded_rectangle([(20, H - 55), (W - 20, H - 20)], radius=12, fill=(30, 45, 75))
    draw.text((W // 2, H - 37), "长按识别小程序码 · 来和 AI 一决高下", fill=TEXT_GRAY, font=font_small, anchor="mm")

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
