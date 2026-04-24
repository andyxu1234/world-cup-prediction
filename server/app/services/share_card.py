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
    
    设计风格：纯白背景、大字、清晰层次、简洁大方
    布局：顶部品牌标签 → 中间大字对战区 → 底部信息+二维码
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 750, 1000

    # 配色 — 纯白极简风
    BG = (255, 255, 255)
    TEXT_BLACK = (30, 30, 30)
    TEXT_GRAY = (100, 100, 100)
    TEXT_LIGHT = (170, 170, 170)
    ACCENT_GREEN = (16, 145, 97)
    ACCENT_BG = (240, 253, 244)
    DIVIDER = (235, 235, 235)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # 字体加载 — 使用更大字号确保清晰可读
    try:
        f_huge = ImageFont.truetype("msyh.ttc", 80)       # 主队名 / 客队名（超大）
        f_vs = ImageFont.truetype("msyh.ttc", 48)          # VS 文字
        f_title = ImageFont.truetype("msyh.ttc", 36)       # 标题文字
        f_body = ImageFont.truetype("msyh.ttc", 28)        # 正文
        f_small = ImageFont.truetype("msyh.ttc", 24)       # 小字（时间等）
        f_tag = ImageFont.truetype("msyh.ttc", 22)         # 标签
        f_tiny = ImageFont.truetype("msyh.ttc", 20)        # 极小字
        f_pred = ImageFont.truetype("msyh.ttc", 26)        # 预测项
    except (OSError, IOError):
        f_huge = f_vs = f_title = f_body = f_small = f_tag = f_tiny = f_pred = ImageFont.load_default()

    # ======== 数据准备 ========
    home = data.get("home_team", "主队")
    away = data.get("away_team", "客队")
    round_text = data.get("round", "")
    match_time = data.get("match_time", "")
    predictions = data.get("predictions", [])

    # 格式化时间
    if match_time:
        try:
            from datetime import datetime, timedelta, timezone
            utc_dt = datetime.fromisoformat(match_time)
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            bj_dt = utc_dt + timedelta(hours=8)
            date_str = bj_dt.strftime("%Y年%m月%d日")
            time_str = bj_dt.strftime("%H:%M")
        except (ValueError, TypeError):
            date_str = match_time[:10]
            time_str = ""
    else:
        date_str = "待定"
        time_str = ""

    # 轮次中文映射
    round_cn_map = {
        "Group Stage - 1": "小组赛第1轮", "Group Stage - 2": "小组赛第2轮",
        "Group Stage - 3": "小组赛第3轮", "Round of 32": "三十二强赛",
        "Round of 16": "十六强赛", "Quarter-finals": "四分之一决赛",
        "Semi-finals": "半决赛", "3rd Place Final": "季军赛", "Final": "决赛",
    }
    round_display = round_cn_map.get(round_text, round_text)

    # ================================================
    #  顶部 — 品牌 + 赛事标题区域
    # ================================================
    top_y = 50

    # 顶部绿色小标签
    tag_w = 220
    tag_h = 44
    tag_x = (W - tag_w) // 2
    draw.rounded_rectangle(
        [(tag_x, top_y), (tag_x + tag_w, top_y + tag_h)],
        radius=22, fill=ACCENT_BG
    )
    draw.text((W // 2, top_y + tag_h // 2), "2026 世界杯 AI 预测",
              fill=ACCENT_GREEN, font=f_small, anchor="mm")

    # ================================================
    #  中间 — 大字对战区（核心视觉焦点）
    # ================================================    
    vs_center_y = 250

    # 主队名（左上）
    home_bbox = draw.textbbox((0, 0), home, font=f_huge)
    home_w = home_bbox[2] - home_bbox[0]
    draw.text((W // 2 - 30 - home_w, vs_center_y), home,
              fill=TEXT_BLACK, font=f_huge, anchor="lt")

    # 客队名（右下）
    draw.text((W // 2 + 30, vs_center_y), away,
              fill=TEXT_BLACK, font=f_huge, anchor="lt")

    # VS 圆形徽章（正中间）
    vs_r = 36
    vs_cx = W // 2
    vs_cy = vs_center_y + 50
    draw.ellipse(
        [(vs_cx - vs_r - 6, vs_cy - vs_r - 6), (vs_cx + vs_r + 6, vs_cy + vs_r + 6)],
        outline=ACCENT_GREEN, width=3
    )
    draw.text((vs_cx, vs_cy), "VS", fill=ACCENT_GREEN, font=f_vs, anchor="mm")

    # ================================================
    #  分割线
    # ================================================
    line_y = 380
    draw.line([(60, line_y), (W - 60, line_y)], fill=DIVIDER, width=1)

    # ================================================
    #  AI 预测摘要区
    # ================================================
    pred_y = line_y + 30
    draw.text((60, pred_y), "AI 预测", fill=TEXT_GRAY, font=f_body, anchor="lt")

    if predictions:
        result_map = {"home_win": "主胜", "draw": "平局", "away_win": "客胜"}
        item_y = pred_y + 46
        
        # 显示前4个预测模型
        for i, p in enumerate(predictions[:4]):
            name = p.get("model_name", "AI")
            res = result_map.get(p.get("result", ""), "?")
            sh = p.get("score_home", "")
            sa = p.get("score_away", "")
            score_str = f" {sh}:{sa}" if str(sh) and str(sa) else ""
            conf = p.get("confidence", 0)
            
            # 模型名
            draw.text((60, item_y), name, fill=TEXT_BLACK, font=f_pred, anchor="lt")
            # 结果
            draw.text((280, item_y), res + score_str, fill=ACCENT_GREEN, font=f_pred, anchor="lt")
            # 信心条
            bar_x = 480
            bar_w = 160
            bar_h = 14
            bar_r = 7
            # 背景
            draw.rounded_rectangle(
                [(bar_x, item_y + 4), (bar_x + bar_w, item_y + 4 + bar_h)],
                radius=bar_r, fill=(245, 245, 245)
            )
            # 填充
            fill_w = int(bar_w * (conf / 10)) if conf else 0
            if fill_w > 0:
                draw.rounded_rectangle(
                    [(bar_x, item_y + 4), (bar_x + fill_w, item_y + 4 + bar_h)],
                    radius=bar_r, fill=ACCENT_GREEN
                )
            # 信心数值
            draw.text((bar_x + bar_w + 12, item_y + 11),
                      f"{conf:.0f}%", fill=TEXT_LIGHT, font=f_tiny, anchor="lt")
            
            item_y += 52

    # ================================================
    #  底部分割线
    # ================================================
    btm_line_y = 680
    draw.line([(60, btm_line_y), (W - 60, btm_line_y)], fill=DIVIDER, width=1)

    # ================================================
    #  底部信息区 — 左侧赛事信息 + 右侧小程序码
    # ================================================
    info_y = btm_line_y + 28

    # 左侧信息
    col_x = 60

    # 比赛名称
    draw.text((col_x, info_y), f"{home}  vs  {away}", fill=TEXT_BLACK, font=f_title, anchor="lt")

    # 日期时间
    dt_y = info_y + 52
    draw.text((col_x, dt_y), f"{date_str}  {time_str}", fill=TEXT_GRAY, font=f_body, anchor="lt")

    # 轮次标签（绿色圆角胶囊）
    tag2_y = dt_y + 42
    tag2_bbox = draw.textbbox((0, 0), round_display, font=f_tag)
    tag2_tw = tag2_bbox[2] - tag2_bbox[0] + 28
    tag2_th = 36
    draw.rounded_rectangle(
        [(col_x, tag2_y), (col_x + tag2_tw, tag2_y + tag2_th)],
        radius=18, fill=ACCENT_BG
    )
    draw.text((col_x + tag2_tw // 2, tag2_y + tag2_th // 2),
              round_display, fill=ACCENT_GREEN, font=f_tag, anchor="mm")

    # ---- 右侧：真实小程序码 ----
    import os
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qr_img_path = os.path.join(_base_dir, "docs", "mini.jpg")

    qr_size = 150
    qr_right = 56
    qr_left_pos = W - qr_right - qr_size
    qr_top_pos = info_y - 8

    try:
        if os.path.exists(qr_img_path):
            qr_img = Image.open(qr_img_path).convert("RGBA")
            qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
            img.paste(qr_img, (qr_left_pos, qr_top_pos), qr_img if qr_img.mode == "RGBA" else None)
            draw = ImageDraw.Draw(img)
        else:
            # 占位框
            draw.rounded_rectangle(
                [(qr_left_pos, qr_top_pos), (qr_left_pos + qr_size, qr_top_pos + qr_size)],
                radius=12, outline=DIVIDER, width=2, fill=(250, 250, 250)
            )
            draw.text((qr_left_pos + qr_size // 2, qr_top_pos + qr_size // 2),
                      "小程序码", fill=TEXT_LIGHT, font=f_tag, anchor="mm")
    except Exception:
        draw.rounded_rectangle(
            [(qr_left_pos, qr_top_pos), (qr_left_pos + qr_size, qr_top_pos + qr_size)],
            radius=12, outline=DIVIDER, width=2, fill=(250, 250, 250)
        )
        draw.text((qr_left_pos + qr_size // 2, qr_top_pos + qr_size // 2),
                  "小程序码", fill=TEXT_LIGHT, font=f_tag, anchor="mm")

    # 二维码下方提示文字
    hint_y = qr_top_pos + qr_size + 14
    draw.text((qr_left_pos + qr_size // 2, hint_y), "长按识别", fill=TEXT_LIGHT, font=f_tiny, anchor="mm")
    draw.text((qr_left_pos + qr_size // 2, hint_y + 24), "查看详情", fill=TEXT_LIGHT, font=f_tiny, anchor="mm")

    # 底部品牌文字
    footer_y = H - 50
    draw.text((W // 2, footer_y), "— AI 预测世界杯 —",
              fill=TEXT_LIGHT, font=f_tiny, anchor="mm")

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
