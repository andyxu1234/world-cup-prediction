"""管理后台路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from pydantic import BaseModel
from typing import Optional

from app.database import get_db, async_session_factory
from app.models.league import League, LeagueType
from app.schemas.league import LeagueOut
from app.services.match_sync import sync_matches
from app.services.odds_service import sync_all_upcoming_odds, sync_league_odds
from app.services.ai_predictor import generate_predictions, generate_single_match_predictions
from app.services.prediction_evaluator import evaluate_predictions
from app.services.stats_sync import sync_standings_and_stats
from app.services.h2h_sync import sync_all_h2h
from app.services.sync_pipeline import sync_matches_and_respond
from app.services.player_stats_sync import sync_all_player_stats, sync_player_master_and_season_stats
from app.services.standings_sync import sync_league_standings
from app.services.polymarket_sync import sync_polymarket_events
from app.services.polymarket_match import match_polymarket_events
from app.services.vip_service import (
    get_vip_status,
    add_vip,
    renew_vip,
    delete_vip,
    get_vip_list,
    get_vip_stats,
)
from app.core.cache import clear_all_caches

router = APIRouter(prefix="/admin", tags=["admin"])


# VIP 相关的请求模型
class AddVipRequest(BaseModel):
    openid: str
    plan_type: str
    remark: Optional[str] = None


class RenewVipRequest(BaseModel):
    user_id: int
    plan_type: str


@router.post("/cache/clear")
async def trigger_clear_cache():
    """手动清空所有缓存（用于代码更新后立即生效）"""
    clear_all_caches()
    return {"message": "All caches cleared"}


@router.post("/pipeline/sync")
async def trigger_sync_pipeline():
    """手动触发完整同步流水线（同步比赛 + 事件驱动下游）"""
    try:
        result = await sync_matches_and_respond()
        return {"status": "ok", "message": "Sync pipeline completed", "detail": result}
    except Exception as e:
        logger.error(f"Sync pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync pipeline failed: {e}")


@router.post("/matches/sync")
async def trigger_sync_matches():
    """手动触发比赛数据同步"""
    try:
        result = await sync_matches()
        return {"status": "ok", "message": "Match sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Match sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Match sync failed: {e}")


@router.post("/polymarket/sync")
async def trigger_sync_polymarket():
    """手动触发 Polymarket 赛事同步 + 与本地比赛匹配（只读，落 polymarket_events 表）"""
    try:
        result = await sync_polymarket_events()
        return {"status": "ok", "message": "Polymarket sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Polymarket sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Polymarket sync failed: {e}")


@router.post("/polymarket/match")
async def trigger_match_polymarket():
    """手动触发 Polymarket 事件与本地 matches 的 DeepSeek 匹配（回填 match_id）

    仅对 polymarket_events.match_id IS NULL 的比赛生效；匹配不上的留 NULL。
    """
    try:
        result = await match_polymarket_events()
        return {"status": "ok", "message": "Polymarket match completed", "detail": result}
    except Exception as e:
        logger.error(f"Polymarket match failed: {e}")
        raise HTTPException(status_code=500, detail=f"Polymarket match failed: {e}")


@router.post("/odds/sync")
async def trigger_sync_odds(odds_type: str = "prematch"):
    """手动触发赔率同步（追加式每日快照，用于构建赔率走势）

    与 scheduler 每日 04:00 的 sync_odds 任务行为一致，可随时手动补拉。
    仅同步未来 7 天内 status=upcoming 的比赛；若窗口内无 upcoming 比赛则跳过。
    """
    try:
        result = await sync_all_upcoming_odds(odds_type=odds_type)
        return {"status": "ok", "message": "Odds sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Odds sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Odds sync failed: {e}")


@router.post("/odds/sync-league")
async def trigger_sync_league_odds(league_id: int = 1, odds_type: str = "prematch"):
    """同步指定联赛全部比赛的赔率（一次性拉全量，不限状态/时间窗口）

    默认 league_id=1（世界杯 2026）。用于补齐历史赛事（如已结束的世界杯）
    的完整赔率快照；与每日增量同步 /odds/sync 互补。
    """
    try:
        result = await sync_league_odds(league_id=league_id, odds_type=odds_type)
        return {"status": "ok", "message": "League odds sync completed", "detail": result}
    except Exception as e:
        logger.error(f"League odds sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"League odds sync failed: {e}")


@router.post("/stats/sync")
async def trigger_sync_stats():
    """手动触发统计同步（积分榜、球队统计、近期状态）"""
    try:
        result = await sync_standings_and_stats()
        return {"status": "ok", "message": "Stats sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Stats sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats sync failed: {e}")


@router.post("/h2h/sync")
async def trigger_sync_h2h():
    """手动触发H2H数据同步"""
    try:
        result = await sync_all_h2h()
        return {"status": "ok", "message": "H2H sync completed", "detail": result}
    except Exception as e:
        logger.error(f"H2H sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"H2H sync failed: {e}")


@router.post("/player-stats/sync")
async def trigger_sync_player_stats(body: Optional[dict] = None):
    """手动触发球员盒子分同步（全量重建所有活跃联赛的球员榜数据）

    可选请求体 {"league_ids": [id, ...]} 仅重建指定联赛（用于回填历史赛季副本）。
    """
    league_ids = (body or {}).get("league_ids") if body else None
    try:
        result = await sync_all_player_stats(league_ids=league_ids)
        return {"status": "ok", "message": "Player stats sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Player stats sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Player stats sync failed: {e}")


@router.post("/standings/sync")
async def trigger_sync_standings(body: Optional[dict] = None):
    """手动触发官方积分榜同步（拉取 /standings 落地 league_standings 表）

    可选请求体 {"league_ids": [id, ...]} 仅同步指定联赛（用于回填历史赛季副本）。
    """
    league_ids = (body or {}).get("league_ids") if body else None
    try:
        result = await sync_league_standings(league_ids=league_ids)
        return {"status": "ok", "message": "Standings sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Standings sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Standings sync failed: {e}")


@router.post("/players/season-stats/sync")
async def trigger_sync_player_season_stats():
    """手动触发球员赛季快照重算（由现有 match_player_stats 聚合，不重新拉 box-score）"""
    try:
        result = await sync_player_master_and_season_stats()
        return {"status": "ok", "message": "Player season stats sync completed", "detail": result}
    except Exception as e:
        logger.error(f"Player season stats sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Player season stats sync failed: {e}")


# ==================== 历史赛季回填（多赛季支持） ====================

class CloneLeagueRequest(BaseModel):
    source_league_id: int
    season: int
    is_active: bool = False


class BackfillSeasonRequest(BaseModel):
    source_league_id: int
    season: int
    with_players: bool = True
    is_active: bool = False


class CreateLeagueRequest(BaseModel):
    """创建一个 Highlightly 上从未同步过的新联赛（区别于 clone：clone 是同联赛换赛季）"""

    name: str
    cn_name: str
    highlightly_league_id: int
    season: int
    type: str  # "league" 或 "cup"
    logo: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


async def _clone_league_row(source_league_id: int, season: int, is_active: bool) -> League:
    """克隆一个联赛行到指定赛季（用于历史赛季回填）。

    若同 (highlightly_league_id, season) 已存在则直接返回已有行（幂等）。
    """
    async with async_session_factory() as session:
        src = (
            await session.execute(select(League).where(League.id == source_league_id))
        ).scalar_one_or_none()
        if src is None:
            raise ValueError(f"League {source_league_id} not found")
        existing = (
            await session.execute(
                select(League).where(
                    League.highlightly_league_id == src.highlightly_league_id,
                    League.season == season,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        new = League(
            name=src.name,
            cn_name=src.cn_name,
            logo=src.logo,
            highlightly_league_id=src.highlightly_league_id,
            season=season,
            type=src.type,
            country=src.country,
            is_active=is_active,
            sort_order=src.sort_order,
        )
        session.add(new)
        await session.commit()
        await session.refresh(new)
        return new


@router.post("/leagues/clone")
async def clone_league(req: CloneLeagueRequest):
    """克隆一个联赛到指定赛季（默认 is_active=False，不影响当前赛季与预测流水线）

    用于在不干扰当前赛季同步/预测的前提下，把历史赛季（如 2025）作为独立联赛行加入，
    以便数据中心展示该赛季的积分榜 / 球员榜。
    """
    try:
        league = await _clone_league_row(req.source_league_id, req.season, req.is_active)
        return {"status": "ok", "league": LeagueOut.from_orm(league)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Clone league failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clone league failed: {e}")


@router.post("/leagues/backfill-season")
async def backfill_season(req: BackfillSeasonRequest):
    """一键回填历史赛季数据（克隆联赛行 + 同步积分榜 + 可选同步比赛/球员榜）

    流程：
      1. 克隆 source_league 到指定 season（is_active 默认 False）
      2. 同步该赛季官方积分榜（league_standings）
      3. 若 with_players=True：同步该赛季比赛（matches）→ 拉盒子分（match_player_stats）→ 重建球员赛季快照

    这样数据中心即可展示例如 2025 赛季的五大联赛 / 欧冠欧联数据，而不影响 2026 当前赛季。
    """
    try:
        league = await _clone_league_row(req.source_league_id, req.season, req.is_active)
        new_id = league.id
        result: dict = {"league_id": new_id, "league_name": league.cn_name, "season": league.season}

        standings_res = await sync_league_standings(league_ids=[new_id])
        result["standings"] = standings_res

        if req.with_players:
            matches_res = await sync_matches(league_id=new_id, season=req.season)
            players_res = await sync_all_player_stats(league_ids=[new_id])
            result["matches"] = matches_res
            result["players"] = players_res

        clear_all_caches()
        return {"status": "ok", "message": "Season backfill completed", "detail": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Season backfill failed: {e}")
        raise HTTPException(status_code=500, detail=f"Season backfill failed: {e}")


@router.post("/leagues/create")
async def create_league(req: CreateLeagueRequest):
    """创建一个全新联赛（新 highlightly_league_id），区别于 clone（同联赛换赛季）

    用于接入 Highlightly 上从未同步过的联赛；元数据全部由调用方提供。
    按 (highlightly_league_id, season) 幂等去重：已存在则返回已有行，不重复插入。
    """
    async with async_session_factory() as session:
        existing = (
            await session.execute(
                select(League).where(
                    League.highlightly_league_id == req.highlightly_league_id,
                    League.season == req.season,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"status": "exists", "league": LeagueOut.from_orm(existing)}
        try:
            lg_type = LeagueType(req.type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid type: {req.type}, must be 'league' or 'cup'",
            )
        new = League(
            name=req.name,
            cn_name=req.cn_name,
            logo=req.logo,
            highlightly_league_id=req.highlightly_league_id,
            season=req.season,
            type=lg_type,
            country=req.country,
            is_active=req.is_active,
            sort_order=req.sort_order,
        )
        session.add(new)
        await session.commit()
        await session.refresh(new)
        clear_all_caches()
        return {"status": "created", "league": LeagueOut.from_orm(new)}


@router.post("/predictions/generate")
async def trigger_generate_predictions():
    """手动触发全部 AI 预测生成"""
    try:
        result = await generate_predictions()
        return {"status": "ok", "message": "Prediction generation completed", "detail": result}
    except Exception as e:
        logger.error(f"Prediction generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction generation failed: {e}")


@router.post("/predictions/generate/{match_id}")
async def trigger_generate_single_match(match_id: int):
    """手动触发单场比赛的 AI 预测"""
    try:
        result = await generate_single_match_predictions(match_id)
        return {"status": "ok", "message": f"Prediction generation completed for match {match_id}", "detail": result}
    except Exception as e:
        logger.error(f"Prediction generation for match {match_id} failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction generation failed: {e}")


@router.post("/predictions/evaluate")
async def trigger_evaluate_predictions():
    """手动触发预测评估"""
    try:
        result = await evaluate_predictions()
        return {"status": "ok", "message": "Prediction evaluation completed", "detail": result}
    except Exception as e:
        logger.error(f"Prediction evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction evaluation failed: {e}")


@router.post("/predictions/reevaluate")
async def trigger_reevaluate_predictions():
    """重新评估所有预测（修复比分命中率计算，考虑备选比分）"""
    try:
        result = await evaluate_predictions(force_recalculate=True)
        return {"status": "ok", "message": "Predictions re-evaluated with alt score logic", "detail": result}
    except Exception as e:
        logger.error(f"Prediction re-evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction re-evaluation failed: {e}")


# ==================== VIP 管理接口 ====================

@router.post("/vip/add")
async def add_vip_member(
    request: AddVipRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加 VIP 会员"""
    try:
        result = await add_vip(
            db=db,
            openid=request.openid,
            plan_type=request.plan_type,
            remark=request.remark,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"添加 VIP 会员失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加失败: {e}")


@router.get("/vip/list")
async def get_vip_members(
    db: AsyncSession = Depends(get_db),
):
    """获取 VIP 会员列表"""
    try:
        members = await get_vip_list(db=db)
        return members
    except Exception as e:
        logger.error(f"获取 VIP 列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {e}")


@router.post("/vip/renew")
async def renew_vip_member(
    request: RenewVipRequest,
    db: AsyncSession = Depends(get_db),
):
    """续费 VIP 会员"""
    try:
        result = await renew_vip(
            db=db,
            user_id=request.user_id,
            plan_type=request.plan_type,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"续费 VIP 会员失败: {e}")
        raise HTTPException(status_code=500, detail=f"续费失败: {e}")


@router.delete("/vip/{member_id}")
async def delete_vip_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除 VIP 会员"""
    try:
        result = await delete_vip(db=db, member_id=member_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"删除 VIP 会员失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.get("/vip/stats")
async def get_vip_statistics(
    db: AsyncSession = Depends(get_db),
):
    """获取 VIP 统计信息"""
    try:
        stats = await get_vip_stats(db=db)
        return stats
    except Exception as e:
        logger.error(f"获取 VIP 统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {e}")


# ==================== Telegram 推送接口 ====================

@router.get("/telegram/test")
async def test_telegram_connection():
    """测试 Telegram Bot 连接

    验证 Bot Token 是否有效，并返回 Bot 信息。
    """
    from app.services.telegram_service import get_telegram_service

    telegram = get_telegram_service()
    bot_info = await telegram.get_me()

    if bot_info:
        return {
            "status": "ok",
            "message": "Telegram Bot 连接成功",
            "bot": {
                "id": bot_info.get("id"),
                "username": bot_info.get("username"),
                "first_name": bot_info.get("first_name"),
            },
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Telegram Bot 连接失败，请检查 BOT_TOKEN 配置"
        )


@router.post("/telegram/push")
async def trigger_telegram_push():
    """手动触发 Telegram 每日推送

    立即执行每日推送任务，用于测试或补发。
    """
    from app.services.telegram_daily_push import daily_push

    try:
        await daily_push()
        return {"status": "ok", "message": "Telegram 推送已执行"}
    except Exception as e:
        logger.error(f"Telegram 推送失败: {e}")
        raise HTTPException(status_code=500, detail=f"Telegram 推送失败: {e}")


@router.post("/telegram/send")
async def send_telegram_message(message: str):
    """发送自定义消息到 Telegram

    Args:
        message: 要发送的消息内容（支持 Markdown 格式）
    """
    from app.services.telegram_service import get_telegram_service

    telegram = get_telegram_service()

    if not telegram.settings.TELEGRAM_CHAT_IDS:
        raise HTTPException(
            status_code=400,
            detail="Telegram Chat IDs 未配置"
        )

    try:
        result = await telegram.broadcast(message)
        return {
            "status": "ok",
            "message": "消息发送完成",
            "detail": result,
        }
    except Exception as e:
        logger.error(f"Telegram 消息发送失败: {e}")
        raise HTTPException(status_code=500, detail=f"消息发送失败: {e}")


@router.get("/telegram/status")
async def get_telegram_status():
    """获取 Telegram 推送配置状态

    返回当前配置信息（隐藏敏感信息）。
    """
    from app.config import get_settings

    settings = get_settings()

    has_token = bool(settings.TELEGRAM_BOT_TOKEN)
    chat_ids = [
        cid.strip()
        for cid in settings.TELEGRAM_CHAT_IDS.split(",")
        if cid.strip()
    ] if settings.TELEGRAM_CHAT_IDS else []

    return {
        "status": "ok",
        "config": {
            "bot_token_configured": has_token,
            "chat_ids_count": len(chat_ids),
            "chat_ids": chat_ids,  # Chat ID 不是敏感信息，可以显示
        },
    }
