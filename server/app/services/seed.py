"""种子数据 — 初始化 AI 模型、模拟比赛和预测"""

from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import async_session_factory
from app.models.ai_model import AIModel
from app.models.team import Team
from app.models.match import Match, MatchStatus, MatchResult
from app.models.prediction import Prediction, PredictionResult

SEED_MODELS = [
    {
        "name": "DeepSeek",
        "model_id": "deepseek/deepseek-v3.2",
        "style_tags": {"origin": "🇨🇳", "style": "性价比之王"},
    },
    {
        "name": "通义千问",
        "model_id": "bailian/qwen3.5-plus",
        "style_tags": {"origin": "🇨🇳", "style": "阿里旗舰"},
    },
    {
        "name": "智谱GLM",
        "model_id": "z-ai/glm-4.7-flash:free",
        "style_tags": {"origin": "🇨🇳", "style": "推理能力强"},
    },
    {
        "name": "Claude",
        "model_id": "anthropic/claude-sonnet-4.6",
        "style_tags": {"origin": "🇺🇸", "style": "Anthropic 旗舰"},
    },
    {
        "name": "GPT",
        "model_id": "openai/gpt-5.2",
        "style_tags": {"origin": "🇺🇸", "style": "OpenAI 旗舰"},
    },
    {
        "name": "Gemini",
        "model_id": "google/gemini-2.5-pro",
        "style_tags": {"origin": "🇺🇸", "style": "Google 旗舰"},
    },
    {
        "name": "Grok",
        "model_id": "openai/gpt-5.2",
        "style_tags": {"origin": "🇺🇸", "style": "xAI出品(暂用GPT替代)"},
    },
    {
        "name": "豆包",
        "model_id": "volcengine/doubao-seed-1-6",
        "style_tags": {"origin": "🇨🇳", "style": "字节跳动"},
    },
    {
        "name": "混元",
        "model_id": "openai/gpt-5.2",
        "style_tags": {"origin": "🇨🇳", "style": "腾讯出品(暂用GPT替代)"},
    },
    {
        "name": "Kimi",
        "model_id": "moonshotai/kimi-k2.5",
        "style_tags": {"origin": "🇨🇳", "style": "月之暗面"},
    },
    {
        "name": "MiniMax",
        "model_id": "minimax/minimax-m2.7",
        "style_tags": {"origin": "🇨🇳", "style": "稀宇科技"},
    },
    {
        "name": "小米 mimo",
        "model_id": "openai/gpt-5.2",
        "style_tags": {"origin": "🇨🇳", "style": "小米出品(暂用GPT替代)"},
    },
]

SEED_TEAMS = [
    {"name": "Brazil", "group_name": "A", "fifa_rank": 1},
    {"name": "Germany", "group_name": "A", "fifa_rank": 3},
    {"name": "Argentina", "group_name": "B", "fifa_rank": 2},
    {"name": "France", "group_name": "B", "fifa_rank": 4},
    {"name": "Spain", "group_name": "C", "fifa_rank": 5},
    {"name": "England", "group_name": "C", "fifa_rank": 6},
    {"name": "Portugal", "group_name": "D", "fifa_rank": 7},
    {"name": "Netherlands", "group_name": "D", "fifa_rank": 8},
    {"name": "Italy", "group_name": "E", "fifa_rank": 9},
    {"name": "Mexico", "group_name": "E", "fifa_rank": 12},
    {"name": "Japan", "group_name": "F", "fifa_rank": 18},
    {"name": "South Korea", "group_name": "F", "fifa_rank": 22},
    {"name": "USA", "group_name": "G", "fifa_rank": 13},
    {"name": "Morocco", "group_name": "G", "fifa_rank": 14},
    {"name": "Senegal", "group_name": "H", "fifa_rank": 20},
    {"name": "Australia", "group_name": "H", "fifa_rank": 30},
]

# 模拟比赛（部分已结束、部分进行中、部分即将开始）
SEED_MATCHES = [
    # 已结束的比赛 — 小组赛第1轮
    {"home": "Brazil", "away": "Germany", "round": "小组赛", "day": 1,
     "status": MatchStatus.finished, "home_score": 2, "away_score": 1, "result": MatchResult.home_win,
     "venue": "SoFi Stadium"},
    {"home": "Argentina", "away": "France", "round": "小组赛", "day": 1,
     "status": MatchStatus.finished, "home_score": 1, "away_score": 1, "result": MatchResult.draw,
     "venue": "MetLife Stadium"},
    {"home": "Spain", "away": "England", "round": "小组赛", "day": 2,
     "status": MatchStatus.finished, "home_score": 3, "away_score": 0, "result": MatchResult.home_win,
     "venue": "AT&T Stadium"},
    {"home": "Portugal", "away": "Netherlands", "round": "小组赛", "day": 2,
     "status": MatchStatus.finished, "home_score": 1, "away_score": 2, "result": MatchResult.away_win,
     "venue": "Hard Rock Stadium"},
    {"home": "Italy", "away": "Mexico", "round": "小组赛", "day": 3,
     "status": MatchStatus.finished, "home_score": 0, "away_score": 1, "result": MatchResult.away_win,
     "venue": "Lumen Field"},
    {"home": "Japan", "away": "South Korea", "round": "小组赛", "day": 3,
     "status": MatchStatus.finished, "home_score": 2, "away_score": 2, "result": MatchResult.draw,
     "venue": "NRG Stadium"},
    # 已结束的比赛 — 小组赛第2轮
    {"home": "Brazil", "away": "Argentina", "round": "小组赛", "day": 4,
     "status": MatchStatus.finished, "home_score": 1, "away_score": 0, "result": MatchResult.home_win,
     "venue": "Mercedes-Benz Stadium"},
    {"home": "Germany", "away": "France", "round": "小组赛", "day": 4,
     "status": MatchStatus.finished, "home_score": 2, "away_score": 2, "result": MatchResult.draw,
     "venue": "Lincoln Financial Field"},
    # 进行中
    {"home": "USA", "away": "Morocco", "round": "小组赛", "day": 5,
     "status": MatchStatus.live, "home_score": 1, "away_score": 0, "result": None,
     "venue": "Rose Bowl"},
    # 即将开始
    {"home": "Senegal", "away": "Australia", "round": "小组赛", "day": 5,
     "status": MatchStatus.upcoming, "home_score": None, "away_score": None, "result": None,
     "venue": "Gillette Stadium"},
    {"home": "Spain", "away": "Portugal", "round": "小组赛", "day": 6,
     "status": MatchStatus.upcoming, "home_score": None, "away_score": None, "result": None,
     "venue": "State Farm Stadium"},
    {"home": "England", "away": "Netherlands", "round": "小组赛", "day": 6,
     "status": MatchStatus.upcoming, "home_score": None, "away_score": None, "result": None,
     "venue": "SoFi Stadium"},
    # 淘汰赛
    {"home": "Brazil", "away": "Spain", "round": "淘汰赛", "day": 10,
     "status": MatchStatus.upcoming, "home_score": None, "away_score": None, "result": None,
     "venue": "MetLife Stadium"},
    {"home": "Argentina", "away": "Portugal", "round": "淘汰赛", "day": 10,
     "status": MatchStatus.upcoming, "home_score": None, "away_score": None, "result": None,
     "venue": "Hard Rock Stadium"},
]

# 模拟预测数据（为已结束的比赛生成）
SEED_PREDICTIONS = {
    # "Brazil vs Germany" — 不同 AI 有不同预测
    ("Brazil", "Germany", 1): [
        {"model": "DeepSeek", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 8, "analysis": "巴西整体实力占优，主场优势明显，预计小胜。"},
        {"model": "通义千问", "result": PredictionResult.home_win, "home_score": 1, "away_score": 0, "confidence": 6, "analysis": "巴西攻防均衡，德国防线存在隐患。"},
        {"model": "智谱GLM", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 7, "analysis": "两队实力接近，大概率平局收场。"},
        {"model": "Claude", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 7, "analysis": "巴西锋线火力更猛，但德国不会轻易放弃。"},
        {"model": "GPT", "result": PredictionResult.away_win, "home_score": 0, "away_score": 2, "confidence": 5, "analysis": "德国战术纪律性更强，有望客场取胜。"},
    ],
    ("Argentina", "France", 1): [
        {"model": "DeepSeek", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 7, "analysis": "阿根廷和法国势均力敌，平局最可能。"},
        {"model": "通义千问", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 6, "analysis": "梅西领衔的阿根廷进攻更具威胁。"},
        {"model": "智谱GLM", "result": PredictionResult.draw, "home_score": 0, "away_score": 0, "confidence": 5, "analysis": "两队防守都很稳固，可能互交白卷。"},
        {"model": "Claude", "result": PredictionResult.away_win, "home_score": 1, "away_score": 2, "confidence": 6, "analysis": "法国整体阵容深度更胜一筹。"},
        {"model": "GPT", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 8, "analysis": "上届决赛重演，双方都会更保守。"},
    ],
    ("Spain", "England", 2): [
        {"model": "DeepSeek", "result": PredictionResult.home_win, "home_score": 3, "away_score": 1, "confidence": 8, "analysis": "西班牙传控体系成熟，英格兰防线漏洞多。"},
        {"model": "通义千问", "result": PredictionResult.home_win, "home_score": 2, "away_score": 0, "confidence": 7, "analysis": "西班牙主场优势大，零封可能性高。"},
        {"model": "智谱GLM", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 6, "analysis": "西班牙整体实力占优，但英格兰有反击威胁。"},
        {"model": "Claude", "result": PredictionResult.home_win, "home_score": 3, "away_score": 0, "confidence": 9, "analysis": "西班牙攻击群状态火热，大胜可期。"},
        {"model": "GPT", "result": PredictionResult.home_win, "home_score": 1, "away_score": 0, "confidence": 6, "analysis": "西班牙略占上风，但差距不大。"},
    ],
    ("Portugal", "Netherlands", 2): [
        {"model": "DeepSeek", "result": PredictionResult.away_win, "home_score": 0, "away_score": 2, "confidence": 7, "analysis": "荷兰全攻全守更成熟，葡萄牙过度依赖个人。"},
        {"model": "通义千问", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 6, "analysis": "两队实力相近，平局概率最高。"},
        {"model": "智谱GLM", "result": PredictionResult.away_win, "home_score": 1, "away_score": 2, "confidence": 7, "analysis": "荷兰中场控制力更强，客场可取胜。"},
        {"model": "Claude", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 5, "analysis": "葡萄牙主场作战有一定优势。"},
        {"model": "GPT", "result": PredictionResult.away_win, "home_score": 1, "away_score": 3, "confidence": 8, "analysis": "荷兰进攻多点开花，葡萄牙防线难以招架。"},
    ],
    ("Italy", "Mexico", 3): [
        {"model": "DeepSeek", "result": PredictionResult.home_win, "home_score": 1, "away_score": 0, "confidence": 7, "analysis": "意大利防守稳固，墨西哥难以破门。"},
        {"model": "通义千问", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 6, "analysis": "意大利整体实力占优。"},
        {"model": "智谱GLM", "result": PredictionResult.draw, "home_score": 0, "away_score": 0, "confidence": 5, "analysis": "两队风格保守，可能互交白卷。"},
        {"model": "Claude", "result": PredictionResult.home_win, "home_score": 1, "away_score": 0, "confidence": 8, "analysis": "意大利大赛经验丰富，一球小胜。"},
        {"model": "GPT", "result": PredictionResult.away_win, "home_score": 0, "away_score": 1, "confidence": 9, "analysis": "墨西哥速度优势明显，反击制胜！信心十足！"},
    ],
    ("Japan", "South Korea", 3): [
        {"model": "DeepSeek", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 7, "analysis": "亚洲德比，实力在伯仲之间。"},
        {"model": "通义千问", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 6, "analysis": "日本技战术更细腻。"},
        {"model": "智谱GLM", "result": PredictionResult.draw, "home_score": 2, "away_score": 2, "confidence": 6, "analysis": "两队都擅长进攻，高比分平局。"},
        {"model": "Claude", "result": PredictionResult.home_win, "home_score": 1, "away_score": 0, "confidence": 5, "analysis": "日本主场优势微弱。"},
        {"model": "GPT", "result": PredictionResult.away_win, "home_score": 1, "away_score": 3, "confidence": 8, "analysis": "韩国体能和对抗能力更强，客场大胜。"},
    ],
    ("Brazil", "Argentina", 4): [
        {"model": "DeepSeek", "result": PredictionResult.home_win, "home_score": 2, "away_score": 1, "confidence": 7, "analysis": "巴西整体实力和主场优势使其略占上风。"},
        {"model": "通义千问", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 6, "analysis": "南美德比，双方都会谨慎。"},
        {"model": "智谱GLM", "result": PredictionResult.home_win, "home_score": 1, "away_score": 0, "confidence": 6, "analysis": "巴西防守更稳固，小胜可能。"},
        {"model": "Claude", "result": PredictionResult.away_win, "home_score": 0, "away_score": 1, "confidence": 9, "analysis": "阿根廷大赛心理素质更强，客场也能赢！"},
        {"model": "GPT", "result": PredictionResult.draw, "home_score": 0, "away_score": 0, "confidence": 5, "analysis": "两队互相忌惮，可能闷平。"},
    ],
    ("Germany", "France", 4): [
        {"model": "DeepSeek", "result": PredictionResult.draw, "home_score": 2, "away_score": 2, "confidence": 7, "analysis": "欧洲双雄对决，进球大战后握手言和。"},
        {"model": "通义千问", "result": PredictionResult.home_win, "home_score": 3, "away_score": 1, "confidence": 6, "analysis": "德国主场进攻火力凶猛。"},
        {"model": "智谱GLM", "result": PredictionResult.away_win, "home_score": 1, "away_score": 3, "confidence": 8, "analysis": "法国锋线实力碾压，客场大胜。"},
        {"model": "Claude", "result": PredictionResult.draw, "home_score": 1, "away_score": 1, "confidence": 6, "analysis": "两队互相制衡，平局合理。"},
        {"model": "GPT", "result": PredictionResult.draw, "home_score": 2, "away_score": 2, "confidence": 7, "analysis": "攻守平衡，各进两球。"},
    ],
}


async def seed_all():
    """一键初始化所有种子数据"""
    await seed_ai_models()
    await seed_teams()
    await seed_matches()
    await seed_predictions()


async def seed_ai_models():
    """初始化 AI 模型数据（合并模式：已存在的跳过，不存在的插入）"""
    from loguru import logger
    async with async_session_factory() as session:
        for model_data in SEED_MODELS:
            stmt = select(AIModel).where(AIModel.model_id == model_data["model_id"])
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                model = AIModel(**model_data)
                session.add(model)
                logger.info(f"Seeded AI model: {model_data['name']}")
        await session.commit()


async def seed_teams():
    """初始化球队数据（合并模式）"""
    from loguru import logger
    async with async_session_factory() as session:
        for team_data in SEED_TEAMS:
            stmt = select(Team).where(Team.name == team_data["name"])
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                team = Team(**team_data)
                session.add(team)
                logger.info(f"Seeded team: {team_data['name']}")
        await session.commit()


async def seed_matches():
    """初始化模拟比赛数据（合并模式：按 home+away+day 去重，不覆盖已有记录）"""
    from loguru import logger
    async with async_session_factory() as session:
        # 获取球队 ID 映射
        team_map = {}
        stmt = select(Team)
        result = await session.execute(stmt)
        for team in result.scalars().all():
            team_map[team.name] = team.id

        base_time = datetime(2026, 6, 11, 18, 0, 0)  # 世界杯开赛日
        inserted = 0
        for match_data in SEED_MATCHES:
            home_id = team_map.get(match_data["home"])
            away_id = team_map.get(match_data["away"])
            if not home_id or not away_id:
                logger.warning(f"Skip match {match_data['home']} vs {match_data['away']}: team not found")
                continue

            # 检查是否已存在相同主客队的比赛（避免重复插入）
            exist_stmt = select(Match).where(
                Match.home_team_id == home_id,
                Match.away_team_id == away_id,
                Match.match_day == match_data["day"],
            )
            exist_result = await session.execute(exist_stmt)
            if exist_result.scalar_one_or_none():
                continue

            match_time = base_time + timedelta(days=match_data["day"] - 1)
            match = Match(
                match_day=match_data["day"],
                round=match_data["round"],
                home_team_id=home_id,
                away_team_id=away_id,
                match_time=match_time,
                venue=match_data.get("venue"),
                status=match_data["status"],
                home_score=match_data.get("home_score"),
                away_score=match_data.get("away_score"),
                result=match_data.get("result"),
            )
            session.add(match)
            inserted += 1

        await session.commit()
        logger.info(f"Seeded {inserted} matches (skipped existing)")


async def seed_predictions():
    """初始化模拟预测数据（合并模式：按 match_id + model_id 去重）"""
    from loguru import logger
    async with async_session_factory() as session:
        # 获取 AI 模型映射
        model_map = {}
        stmt = select(AIModel)
        result = await session.execute(stmt)
        for model in result.scalars().all():
            model_map[model.name] = model.id

        # 获取比赛映射 (home_team_name, away_team_name, day) -> match_id
        match_map = {}
        stmt = select(Match)
        result = await session.execute(stmt)
        for match in result.scalars().all():
            home_stmt = select(Team).where(Team.id == match.home_team_id)
            away_stmt = select(Team).where(Team.id == match.away_team_id)
            home_result = await session.execute(home_stmt)
            away_result = await session.execute(away_stmt)
            home_team = home_result.scalar_one()
            away_team = away_result.scalar_one()
            match_map[(home_team.name, away_team.name, match.match_day)] = match.id

        count = 0
        for (home, away, day), preds in SEED_PREDICTIONS.items():
            match_id = match_map.get((home, away, day))
            if not match_id:
                logger.warning(f"Skip predictions for {home} vs {away} day {day}: match not found")
                continue

            # 获取比赛结果，用于自动评估
            match_obj = None
            for m_data in SEED_MATCHES:
                if m_data["home"] == home and m_data["away"] == away and m_data["day"] == day:
                    match_obj = m_data
                    break

            for pred_data in preds:
                model_id = model_map.get(pred_data["model"])
                if not model_id:
                    logger.warning(f"Skip prediction: model {pred_data['model']} not found")
                    continue

                # 按 match_id + model_id 去重，已存在的预测跳过
                exist_stmt = select(Prediction).where(
                    Prediction.match_id == match_id,
                    Prediction.model_id == model_id,
                )
                exist_result = await session.execute(exist_stmt)
                if exist_result.scalar_one_or_none():
                    continue

                # 自动评估：仅当比赛已结束时计算正确性
                is_correct_result = None
                is_correct_score = None
                if match_obj and match_obj["status"] == MatchStatus.finished:
                    pred_res = pred_data["result"]
                    actual_res = match_obj.get("result")
                    is_correct_result = (pred_res == actual_res)
                    if pred_data.get("home_score") == match_obj.get("home_score") \
                            and pred_data.get("away_score") == match_obj.get("away_score"):
                        is_correct_score = True
                    else:
                        is_correct_score = False

                prediction = Prediction(
                    match_id=match_id,
                    model_id=model_id,
                    result=pred_data["result"],
                    score_home=pred_data.get("home_score"),
                    score_away=pred_data.get("away_score"),
                    confidence=pred_data.get("confidence"),
                    analysis=pred_data.get("analysis"),
                    is_correct_result=is_correct_result,
                    is_correct_score=is_correct_score,
                )
                session.add(prediction)
                count += 1

        await session.commit()
        logger.info(f"Seeded {count} predictions (skipped existing)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_all())
