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
    """用 Pillow 生成分享卡片图片，返回 PNG 字节流"""
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
