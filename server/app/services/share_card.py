"""分享卡片生成服务"""

from __future__ import annotations

import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.match import Match
from app.models.prediction import Prediction
from app.models.ai_model import AIModel


def _load_font(size):
    """加载中文字体，按优先级尝试多种路径（兼容 Windows/Linux/macOS）"""
    from PIL import ImageFont
    _font_paths = [
        "msyh.ttc",                                    # Windows 微软雅黑
        "msyhbd.ttc",                                  # Windows 微软雅黑粗体
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",   # Linux 文泉驿微米黑
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto CJK
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",  # Linux 文鼎
        "/System/Library/Fonts/PingFang.ttc",          # macOS 苹方
    ]
    for fp in _font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


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
    """用 Pillow 生成分享卡片图片（比赛信息卡），返回 PNG 字节流
    
    设计方向：Sports Editorial / 赛事转播图形风格
    - 深绿渐变顶部品牌栏（与小程序主题一致）
    - 大胆的队名排版 + VS 圆形徽章
    - 卡片式 AI 预测区
    - 底部深色 Footer 嵌入小程序码
    """
    from PIL import Image, ImageDraw, ImageFont
    import os
    import math

    W, H = 750, 1060  # 拉长卡片

    # ===== 配色（浅化绿色）=====
    GREEN_DARK = (60, 160, 100)       # 浅森林绿（再提亮）
    GREEN_MID = (80, 190, 130)        # 中绿（再提亮）
    GREEN_ACCENT = (22, 163, 96)      # 亮绿点缀
    GOLD = (245, 166, 35)
    BG = (248, 250, 252)             # 浅灰背景
    CARD_WHITE = (255, 255, 255)     # 卡片白
    TEXT_PRIMARY = (15, 23, 42)      # 主文字（近黑）
    TEXT_SECONDARY = (100, 116, 139) # 次文字（石板灰）
    TEXT_MUTED = (180, 190, 205)     # 弱文字
    DIVIDER = (230, 235, 240)        # 分割线

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ===== 字体 =====
    f_brand = _load_font(28)         # 品牌栏文字
    f_round = _load_font(24)         # 轮次标签
    f_name = _load_font(52)          # 队名（大字冲击力）
    f_vs = _load_font(30)            # VS 文字
    f_meta = _load_font(22)          # 时间/场地元信息
    f_pred_title = _load_font(26)    # 区块标题
    f_pred_item = _load_font(26)     # 预测条目文字
    f_score = _load_font(28)         # 比分数字
    f_slogan = _load_font(30)        # 底部标语
    f_slogan_sub = _load_font(20)    # 底部副标语
    f_tag = _load_font(18)           # 标签小字

    # ===== 数据准备 =====
    home = data.get("home_team", "\u4e3b\u961f")
    away = data.get("away_team", "\u5ba2\u961f")
    home_flag_url = data.get("home_flag", "")
    away_flag_url = data.get("away_flag", "")
    round_text = data.get("round", "")

    if data.get("match_time"):
        try:
            from datetime import datetime, timedelta, timezone
            dt = datetime.fromisoformat(data["match_time"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt + timedelta(hours=8)
            time_str = dt.strftime("%m\u6708%d\u65e5 %H:%M")
        except Exception:
            time_str = str(data.get("match_time", ""))[:16]
    else:
        time_str = "\u5f85\u5b9a"

    round_cn = {
        "Group Stage - 1": "\u5c0f\u7ec4\u8d5b\u7b2c1\u8f6e",
        "Group Stage - 2": "\u5c0f\u7ec4\u8d5b\u7b2c2\u8f6e",
        "Group Stage - 3": "\u5c0f\u7ec4\u8d5b\u7b2c3\u8f6e",
        "Round of 32": "\u4e09\u5341\u4e8c\u5f3a\u8d5b",
        "Round of 16": "\u5341\u516d\u5f3a\u8d5b",
        "Quarter-finals": "\u56db\u5206\u4e4b\u4e00\u51b3\u8d5b",
        "Semi-finals": "\u534a\u51b3\u8d5b",
        "Final": "\u51b3\u8d5b",
    }
    round_label = round_cn.get(round_text, round_text)

    # =============================================
    #  [1] 顶部深绿品牌栏（全宽，圆角底部）
    # =============================================
    HEADER_H = 88
    # 绘制顶部圆角矩形作为 Header
    header_radius = 0
    # 上半部分：纯深绿
    draw.rounded_rectangle(
        [(0, 0), (W, HEADER_H)], radius=header_radius, fill=GREEN_DARK
    )
    # 底部加一条亮线装饰
    draw.rectangle([(0, HEADER_H - 3), (W, HEADER_H)], fill=GREEN_ACCENT)

    # 品牌 Logo 文字（左）+ 轮次（右）
    draw.text((32, HEADER_H // 2 - 2),
              "AI \u9884\u6d4b\u4e16\u754c\u676f",
              fill=(255, 255, 255), font=f_brand, anchor="lm")
    # 右侧轮次标签（胶囊形背景）
    round_bb = draw.textbbox((0, 0), round_label, font=f_round)
    round_tw = round_bb[2] - round_bb[0] + 24
    round_th = 32
    round_rx = W - 32 - round_tw
    round_ry = HEADER_H // 2 - round_th // 2
    draw.rounded_rectangle(
        [(round_rx, round_ry), (round_rx + round_tw, round_ry + round_th)],
        radius=round_th // 2, fill=GREEN_ACCENT
    )
    draw.text((round_rx + round_tw // 2, round_ry + round_th // 2),
              round_label, fill=(255, 255, 255), font=f_round, anchor="mm")

    # =============================================
    #  [2] Hero 区：国旗 + 队名 + VS 圆形徽章
    # =============================================
    hero_top = HEADER_H + 40
    FLAG_W, FLAG_H = 140, 95
    gap_between_flags = 80  # 两旗间距（放 VS 圆圈）

    total_hero_w = FLAG_W * 2 + gap_between_flags
    hero_start_x = (W - total_hero_w) // 2

    home_fx = hero_start_x
    away_fx = hero_start_x + FLAG_W + gap_between_flags
    vs_cx = W // 2
    vs_cy = hero_top + FLAG_H // 2
    vs_r = 28  # VS 圆形徽章半径

    def try_load_flag(url):
        if not url:
            return None
        try:
            import urllib.request
            if url.startswith(("http://", "https://")):
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return Image.open(io.BytesIO(resp.read())).convert("RGBA")
            elif os.path.exists(url):
                return Image.open(url).convert("RGBA")
        except Exception:
            pass
        return None

    def paste_rounded_flag(x, y, flag_or_none):
        if flag_or_none is None:
            draw.rounded_rectangle(
                [(x, y), (x + FLAG_W, y + FLAG_H)],
                radius=12, outline=TEXT_MUTED, width=2
            )
            cx, cy = x + FLAG_W // 2, y + FLAG_H // 2
            draw.text((cx, cy), "?", fill=TEXT_SECONDARY, font=_load_font(36), anchor="mm")
            return

        resized = flag_or_none.resize((FLAG_W, FLAG_H), Image.LANCZOS)
        mask = Image.new("L", (FLAG_W, FLAG_H), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([(0, 0), (FLAG_W, FLAG_H)], radius=12, fill=255)
        img.paste(resized, (x, y), mask)

    home_fi = try_load_flag(home_flag_url)
    paste_rounded_flag(home_fx, hero_top, home_fi)
    draw = ImageDraw.Draw(img)

    away_fi = try_load_flag(away_flag_url)
    paste_rounded_flag(away_fx, hero_top, away_fi)
    draw = ImageDraw.Draw(img)

    # --- VS 圆形徽章 ---
    draw.ellipse(
        [(vs_cx - vs_r - 4, vs_cy - vs_r - 4), (vs_cx + vs_r + 4, vs_cy + vs_r + 4)],
        fill=GOLD, outline=GOLD
    )
    draw.ellipse(
        [(vs_cx - vs_r, vs_cy - vs_r), (vs_cx + vs_r, vs_cy + vs_r)],
        fill=CARD_WHITE, outline=GREEN_DARK, width=2
    )
    draw.text((vs_cx, vs_cy + 1), "VS",
              fill=GREEN_DARK, font=f_vs, anchor="mm")

    # --- 队名（国旗下方，加大间距避免重叠）---
    name_y = hero_top + FLAG_H + 42
    draw.text((home_fx + FLAG_W // 2, name_y), home,
              fill=TEXT_PRIMARY, font=f_name, anchor="mm")
    draw.text((away_fx + FLAG_W // 2, name_y), away,
              fill=TEXT_PRIMARY, font=f_name, anchor="mm")

    # =============================================
    #  [3] 时间信息条（细横条）
    # =============================================
    time_y = name_y + 60
    draw.text((W // 2, time_y), time_str,
              fill=TEXT_SECONDARY, font=f_meta, anchor="mm")

    # =============================================
    #  [4] AI 预测区（卡片容器）
    # =============================================
    card_margin = 28
    card_top = time_y + 56
    predictions = data.get("predictions", [])

    if predictions:
        # 计算卡片高度
        pred_count = min(len(predictions), 4)  # 最多显示4个
        row_h = 54
        card_h = 44 + pred_count * row_h + 20

        draw.rounded_rectangle(
            [(card_margin, card_top), (W - card_margin, card_top + card_h)],
            radius=16, fill=CARD_WHITE
        )
        # 卡片微妙阴影效果（用边框模拟）
        draw.rounded_rectangle(
            [(card_margin, card_top), (W - card_margin, card_top + card_h)],
            radius=16, outline=DIVIDER, width=1
        )

        # 区块标题
        title_y = card_top + 28
        draw.text((card_margin + 16, title_y),
                  "AI \u9884\u6d4b\u7ed3\u679c",
                  fill=GREEN_ACCENT, font=f_pred_title, anchor="lm")

        item_y = title_y + 38
        for i, pred in enumerate(predictions[:pred_count]):
            model_name = pred.get("model_name", "AI")
            result = pred.get("result", "")
            score_h = pred.get("score_home", 0)
            score_a = pred.get("score_away", 0)

            result_map = {
                "home_win": "\u4e3b\u80dc", "draw": "\u5e73\u5c40", "away_win": "\u5ba2\u80dc"
            }
            result_text = result_map.get(result, "")

            iy = item_y + i * row_h

            # 左侧：模型名
            draw.text((card_margin + 24, iy), model_name,
                      fill=TEXT_PRIMARY, font=f_pred_item, anchor="lm")
            # 中间：预测结果
            draw.text((W // 2, iy), result_text,
                      fill=GREEN_DARK, font=f_pred_item, anchor="mm")
            # 右侧：比分
            draw.text((W - card_margin - 24, iy), f"{score_h}:{score_a}",
                      fill=TEXT_SECONDARY, font=f_score, anchor="rm")

            # 分隔线
            if i < pred_count - 1:
                line_y = iy + row_h // 2
                draw.line([(card_margin + 20, line_y), (W - card_margin - 20, line_y)],
                         fill=DIVIDER, width=1)
    else:
        # 无预测时显示挑战 CTA 卡片
        card_h = 90
        draw.rounded_rectangle(
            [(card_margin, card_top), (W - card_margin, card_top + card_h)],
            radius=16, fill=CARD_WHITE
        )
        draw.rounded_rectangle(
            [(card_margin, card_top), (W - card_margin, card_top + card_h)],
            radius=16, outline=DIVIDER, width=1
        )
        draw.text((W // 2, card_top + card_h // 2 - 10),
                  "\u5feb\u6765\u6311\u6218\u4e00\u4e0b",
                  fill=GREEN_ACCENT, font=f_slogan, anchor="mm")
        draw.text((W // 2, card_top + card_h // 2 + 22),
                  "\u770b\u770b\u662f\u4f60\u8fd8\u662f AI \u9884\u6d4b\u5f97\u66f4\u51c6\uff01",
                  fill=TEXT_SECONDARY, font=f_meta, anchor="mm")

    # =============================================
    #  [5] 底部 Footer（标语 + 小程序码）
    # =============================================
    footer_h = 140
    footer_top = H - footer_h
    # Footer 背景
    draw.rounded_rectangle(
        [(0, footer_top), (W, H)], radius=0, fill=GREEN_DARK
    )
    # 顶部过渡装饰线
    draw.rectangle([(0, footer_top), (W, footer_top + 3)], fill=GREEN_MID)

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qr_path = os.path.join(base_dir, "avatars", "mini.jpg")

    qrsz = 120
    qrm = 28
    qx = W - qrm - qrsz
    qy = footer_top + (footer_h - qrsz) // 2  # 垂直居中在 footer 内

    # 左侧标语
    sl_cx = (qx - 50) // 2
    sl_cy = footer_top + footer_h // 2
    draw.text((sl_cx, sl_cy - 14),
              "AI \u9884\u6d4b\u4e16\u754c\u676f",
              fill=(255, 255, 255), font=f_slogan, anchor="mm")
    draw.text((sl_cx, sl_cy + 20),
              "\u8c01\u624d\u662f\u6700\u5f3a\u8a00\u5bb6\uff1f",
              fill=(160, 180, 170), font=f_slogan_sub, anchor="mm")

    # 小程序码
    qr_ok = False
    try:
        if os.path.exists(qr_path):
            qi = Image.open(qr_path).convert("RGBA").resize((qrsz, qrsz), Image.LANCZOS)
            # 给二维码加白色圆角背景
            bg_qr = Image.new("RGB", (qrsz + 12, qrsz + 12), (255, 255, 255))
            bg_draw = ImageDraw.Draw(bg_qr)
            bg_draw.rounded_rectangle([(0, 0), (qrsz + 11, qrsz + 11)], radius=12, fill=(255, 255, 255))
            qi_rgb = qi.convert("RGB")
            bg_qr.paste(qi_rgb, (6, 6))
            img.paste(bg_qr, (qx - 6, qy - 6))
            draw = ImageDraw.Draw(img)
            qr_ok = True
    except Exception:
        pass

    if not qr_ok:
        draw.rounded_rectangle(
            [(qx, qy), (qx + qrsz, qy + qrsz)],
            radius=12, outline=(160, 180, 170), width=2
        )
        draw.text((qx + qrsz // 2, qy + qrsz // 2),
                  "\u626b\u7801", fill=(160, 180, 170), font=f_tag, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()


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

    # 加载字体（使用模块级多路径回退）
    font_xl = _load_font(44)
    font_lg = _load_font(32)
    font_md = _load_font(26)
    font_sm = _load_font(20)
    font_xs = _load_font(16)
    font_num = _load_font(52)
    font_num_sm = _load_font(28)

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
