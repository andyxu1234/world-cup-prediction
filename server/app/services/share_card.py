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
    """用 Pillow 生成分享卡片图片（比赛信息卡），返回 PNG 字节流
    
    设计：现代渐变背景，世界杯主题风格
    内容：轮次 → 国旗+队名 VS → 预测结果 → 底部小程序码和标语
    """
    from PIL import Image, ImageDraw, ImageFont
    import os

    W, H = 750, 1000  # 竖版卡片，更适合手机分享

    # ===== 配色（纯白背景，与小程序码融为一体）=====
    WHITE = (255, 255, 255)
    DARK = (30, 41, 59)           # 主文字深色
    GRAY = (148, 163, 184)        # 次要文字灰色
    ACCENT_GREEN = (16, 185, 129) # 绿色点缀
    ACCENT_GOLD = (251, 191, 36)  # 金色点缀
    LIGHT_BG = (248, 250, 252)    # 浅灰背景区

    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # ===== 字体 =====
    try:
        f_title = ImageFont.truetype("msyh.ttc", 32)    # 标题
        f_round = ImageFont.truetype("msyh.ttc", 28)     # 轮次
        f_name = ImageFont.truetype("msyh.ttc", 48)       # 队名
        f_vs = ImageFont.truetype("msyh.ttc", 40)         # VS
        f_pred = ImageFont.truetype("msyh.ttc", 24)       # 预测文字
        f_meta = ImageFont.truetype("msyh.ttc", 22)       # 时间/场地
        f_qr = ImageFont.truetype("msyh.ttc", 18)         # 小程序码文字
    except (OSError, IOError):
        f_title = f_round = f_name = f_vs = f_pred = f_meta = f_qr = ImageFont.load_default()

    # ===== 数据 =====
    home = data.get("home_team", "主队")
    away = data.get("away_team", "客队")
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
            date_str = dt.strftime("%a %b %d %Y")
        except Exception:
            date_str = str(data["match_time"])[:10]
    else:
        date_str = "待定"
    venue_str = data.get("venue") or "TBD"

    round_cn = {
        "Group Stage - 1": "小组赛第1轮",
        "Group Stage - 2": "小组赛第2轮",
        "Group Stage - 3": "小组赛第3轮",
        "Round of 32": "三十二强赛",
        "Round of 16": "十六强赛",
        "Quarter-finals": "四分之一决赛",
        "Semi-finals": "半决赛",
        "Final": "决赛",
    }
    round_label = round_cn.get(round_text, round_text)

    # =============================================
    #  [1] 标题 + 轮次（顶部）
    # =============================================
    draw.text((W // 2, 40), "\u26bd 世界杯 AI 预测大赛", fill=ACCENT_GREEN, font=f_title, anchor="mm")
    draw.text((W // 2, 80), round_label, fill=GRAY, font=f_round, anchor="mm")

    # =============================================
    #  [2] 国旗 + 队名 + VS
    # =============================================
    FLAG_W, FLAG_H = 140, 96
    flag_top = 120
    vs_center_x = W // 2
    gap = 100  # 两旗之间间距

    home_flag_x = vs_center_x - gap // 2 - FLAG_W // 2
    away_flag_x = vs_center_x + gap // 2 + FLAG_W // 2

    def try_load_flag(url):
        """尝试加载国旗图片"""
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

    def paste_flag(x, y, flag_img_or_none):
        """粘贴国旗到指定位置（带圆角）"""
        if flag_img_or_none is None:
            # 无国旗时画半透明占位框
            draw.rounded_rectangle(
                [(x, y), (x + FLAG_W, y + FLAG_H)],
                radius=10, outline=GRAY, width=1
            )
            draw.text((x + FLAG_W // 2, y + FLAG_H // 2),
                      "\u26bd", fill=DARK, font=f_vs, anchor="mm")
            return

        resized = flag_img_or_none.resize((FLAG_W, FLAG_H), Image.LANCZOS)
        # 创建圆角蒙版
        mask = Image.new("L", (FLAG_W, FLAG_H), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle([(0, 0), (FLAG_W, FLAG_H)], radius=10, fill=255)
        # 粘贴
        img.paste(resized, (x, y), mask)

    home_fi = try_load_flag(home_flag_url)
    paste_flag(int(home_flag_x), flag_top, home_fi)
    draw = ImageDraw.Draw(img)  # paste 后重建 draw

    away_fi = try_load_flag(away_flag_url)
    paste_flag(int(away_flag_x), flag_top, away_fi)
    draw = ImageDraw.Draw(img)

    # 队名
    name_y = flag_top + FLAG_H + 16
    draw.text((home_flag_x + FLAG_W // 2, name_y), home,
              fill=DARK, font=f_name, anchor="mm")
    draw.text((away_flag_x + FLAG_W // 2, name_y), away,
              fill=DARK, font=f_name, anchor="mm")

    # VS 文字（正中间）
    draw.text((vs_center_x, flag_top + FLAG_H // 2),
              "VS", fill=GRAY, font=f_vs, anchor="mm")

    # =============================================
    #  [3] 时间（队名下方）
    # =============================================
    meta_y = name_y + 50
    if data.get("match_time"):
        try:
            from datetime import datetime, timedelta, timezone
            dt = datetime.fromisoformat(data["match_time"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt + timedelta(hours=8)
            time_str = dt.strftime("%m月%d日 %H:%M")
        except Exception:
            time_str = str(data["match_time"])[:16]
    else:
        time_str = "待定"
    
    draw.text((W // 2, meta_y), f"{time_str}", fill=GRAY, font=f_meta, anchor="mm")

    # =============================================
    #  [4] AI 预测结果区
    # =============================================
    pred_start_y = meta_y + 60
    predictions = data.get("predictions", [])
    
    if predictions:
        pred_title_y = pred_start_y
        draw.text((W // 2, pred_title_y), "\ud83e\udd16 AI \u9884\u6d4b\u7ed3\u679c", fill=ACCENT_GREEN, font=f_pred, anchor="mm")
        
        pred_item_y = pred_title_y + 40
        for i, pred in enumerate(predictions[:5]):  # 最多显示5个预测
            model_name = pred.get("model_name", "AI")
            result = pred.get("result", "")
            score_h = pred.get("score_home", 0)
            score_a = pred.get("score_away", 0)
            
            # 预测结果文字
            result_text = "主胜" if result == "home_win" else ("平局" if result == "draw" else "客胜")
            
            # 模型名（左）
            draw.text((80, pred_item_y + i * 50), model_name, fill=DARK, font=f_pred, anchor="lm")
            # 预测结果（中）
            draw.text((W // 2, pred_item_y + i * 50), result_text, fill=ACCENT_GREEN, font=f_pred, anchor="mm")
            # 比分（右）
            draw.text((W - 80, pred_item_y + i * 50), f"{score_h}:{score_a}", fill=GRAY, font=f_pred, anchor="rm")
            
            # 分隔线
            if i < len(predictions) - 1 and i < 4:
                draw.line([(60, pred_item_y + i * 50 + 25), (W - 60, pred_item_y + i * 50 + 25)], 
                         fill=GRAY, width=1)
    
    # =============================================
    #  [5] 底部区域：标语（左）+ 小程序码（右下角）
    # =============================================
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qr_path = os.path.join(base_dir, "avatars", "mini.jpg")

    qrsz = 140          # 放大后尺寸
    qrm = 28            # 右下边距
    qx = W - qrm - qrsz
    qy = H - qrm - qrsz

    # 左侧标语（在二维码左边）
    slogan_cx = qx // 2
    slogan_y = qy + qrsz // 2
    draw.text((slogan_cx, slogan_y - 14), "AI \u9884\u6d4b\u4e16\u754c\u676f", fill=DARK, font=f_pred, anchor="mm")
    draw.text((slogan_cx, slogan_y + 14), "\u8c01\u624d\u662f\u6700\u5f3a\u8a00\u5bb6\uff1f", fill=GRAY, font=f_qr, anchor="mm")

    qr_loaded = False
    try:
        if os.path.exists(qr_path):
            qi = Image.open(qr_path).convert("RGBA").resize((qrsz, qrsz), Image.LANCZOS)
            img.paste(qi, (qx, qy), qi if qi.mode == "RGBA" else None)
            draw = ImageDraw.Draw(img)
            qr_loaded = True
    except Exception:
        pass

    if not qr_loaded:
        draw.rounded_rectangle(
            [(qx, qy), (qx + qrsz, qy + qrsz)],
            radius=12, outline=GRAY, width=2
        )
        draw.text((qx + qrsz // 2, qy + qrsz // 2 - 10),
                  "\u626b\u7801", fill=GRAY, font=f_qr, anchor="mm")
        draw.text((qx + qrsz // 2, qy + qrsz // 2 + 14),
                  "\u4f53\u9a8c", fill=GRAY, font=f_qr, anchor="mm")

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
