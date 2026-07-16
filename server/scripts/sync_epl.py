"""英超（Premier League）数据同步脚本 — 在【服务器】上运行

前置：
  - 在 server/ 目录下，激活 venv：source .venv/bin/activate
  - 依赖 app 模块可导入（asyncio + asyncmy + 数据库可达）

用法：
  # 1) 探查 Highlightly 上的英超候选（拿到正确的 hl_id / season）
  python scripts/sync_epl.py discover

  # 2) 新增联赛并同步比赛
  python scripts/sync_epl.py add <hl_id> <season> [--cn-name 英超] [--country England] [--no-sync]

  # 3) 在已存在的联赛上重新同步比赛
  python scripts/sync_epl.py sync <local_league_id>

  # 可选：同步后拉取 H2H、生成 AI 预测（覆盖所有活跃联赛的 upcoming 比赛）
  python scripts/sync_epl.py add <hl_id> <season> --h2h --predict

  # 一键：自动探查并选中「英格兰英超」、新增联赛、同步比赛
  python scripts/sync_epl.py setup [--h2h] [--predict]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 将项目根目录（server/）加入 sys.path，确保 `python scripts/sync_epl.py` 能 import app
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from loguru import logger

from sqlalchemy import select

from app.models.league import League, LeagueType
from app.config import get_settings
from app.core.highlightly import HighlightlyClient

import app.database as _dbmod  # 通过模块属性访问，确保用上 patch 后的引擎


def _patch_engine_no_ssl():
    """Windows 上 asyncmy 的 ssl connect_args 会触发 WinError 87，去掉后正常连接。

    仅 win32 生效；Linux/服务器环境保留 database.py 原生的 ssl 配置。
    """
    if sys.platform != "win32":
        return
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    s = get_settings()
    url = (
        f"mysql+asyncmy://{s.DB_USER}:{s.DB_PASSWORD}"
        f"@{s.DB_HOST}:{s.DB_PORT}/{s.DB_NAME}"
    )
    engine = create_async_engine(url, pool_recycle=3600, pool_size=5, max_overflow=10)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    import app.database as _dbmod
    _dbmod.engine = engine
    _dbmod.async_session_factory = factory
    logger.info("[patch] Windows 环境：已用无 SSL 引擎覆盖 app.database")


# ── 探查 ────────────────────────────────────────────────

async def discover():
    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )
    try:
        offset = 0
        limit = 200
        found = []
        while True:
            data = await client.get_leagues(limit=limit, offset=offset)
            leagues = data.get("data", []) if isinstance(data, dict) else data
            if not leagues:
                break
            for lg in leagues:
                name = (lg.get("name") or "")
                if "premier league" in name.lower():
                    found.append(lg)
            if len(leagues) < limit:
                break
            offset += limit
        if not found:
            print("[discover] 未找到 'Premier League'，请检查 Highlightly 返回或手动指定 hl_id")
            return
        print(f"[discover] 找到 {len(found)} 个候选：")
        for lg in found:
            print(
                f"  hl_id={lg.get('id')}  name={lg.get('name')!r}  "
                f"country={lg.get('country')!r}  season={lg.get('season')}  "
                f"logo={'yes' if lg.get('logo') else 'no'}"
            )
        print("\n下一步：python scripts/sync_epl.py add <hl_id> <season>")
    finally:
        await client.close()


# ── 一键 setup ──────────────────────────────────────────

async def setup(do_h2h: bool, do_predict: bool):
    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )
    try:
        # 1) 探查所有 Premier League 候选
        offset = 0
        limit = 200
        candidates = []
        while True:
            data = await client.get_leagues(limit=limit, offset=offset)
            leagues = data.get("data", []) if isinstance(data, dict) else data
            if not leagues:
                break
            for lg in leagues:
                if "premier league" in (lg.get("name") or "").lower():
                    candidates.append(lg)
            if len(leagues) < limit:
                break
            offset += limit

        if not candidates:
            print("[setup] 未找到 Premier League，请手动指定 hl_id/season")
            return

        # 2) 优先选 country == England
        chosen = next(
            (c for c in candidates if (c.get("country") or "").lower() == "england"),
            candidates[0],
        )
        hl_id = chosen.get("id")
        season = chosen.get("season")
        print(f"[setup] 选中：{chosen.get('name')!r} country={chosen.get('country')!r} "
              f"hl_id={hl_id} season={season}")
    finally:
        await client.close()

    # 3) 新增 + 同步
    await add_league(
        hl_id=hl_id,
        season=season,
        cn_name="英超",
        country="England",
        do_sync=True,
        do_h2h=do_h2h,
        do_predict=do_predict,
    )


# ── 新增联赛 ────────────────────────────────────────────

async def add_league(hl_id: int, season: int, cn_name: str, country: str, do_sync: bool, do_h2h: bool, do_predict: bool):
    async with _dbmod.async_session_factory() as session:
        # 去重：同一 (hl_id, season) 不重复插入
        stmt = select(League).where(
            League.highlightly_league_id == hl_id,
            League.season == season,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            print(f"[add] 联赛已存在：local id={existing.id} ({existing.cn_name})")
            local_id = existing.id
        else:
            league = League(
                name="Premier League",
                cn_name=cn_name,
                logo=None,
                highlightly_league_id=hl_id,
                season=season,
                type=LeagueType.league,
                country=country,
                is_active=True,
                sort_order=10,
            )
            session.add(league)
            await session.commit()
            await session.refresh(league)
            local_id = league.id
            print(f"[add] 已新增联赛：local id={local_id} ({cn_name}) hl_id={hl_id} season={season}")

    if do_sync:
        await run_sync(local_id)
    if do_h2h:
        await run_h2h()
    if do_predict:
        await run_predict()


async def run_sync(local_league_id: int):
    from app.services.match_sync import sync_matches
    print(f"[sync] 开始同步比赛 league_id={local_league_id} ...")
    result = await sync_matches(league_id=local_league_id)
    print(f"[sync] 完成：{result}")


async def run_h2h():
    from app.services.h2h_sync import sync_all_h2h
    print("[h2h] 同步所有比赛 H2H（可能较多 API 调用，注意限流）...")
    h2h = await sync_all_h2h()
    print(f"[h2h] 完成：{h2h}")


async def run_predict():
    from app.services.ai_predictor import generate_predictions
    print("[predict] 生成全量 AI 预测（含英超 upcoming 比赛）...")
    result = await generate_predictions()
    print(f"[predict] 完成：{result}")


async def sync_existing(local_league_id: int, do_h2h: bool, do_predict: bool):
    await run_sync(local_league_id)
    if do_h2h:
        await run_h2h()
    if do_predict:
        await run_predict()


async def predict_league(local_league_id: int, limit: int, do_all: bool):
    """为某联赛的 upcoming 比赛逐场生成 AI 预测（演示用，避开批量仅覆盖 3 天的限制）"""
    from app.services.ai_predictor import generate_single_match_predictions
    from app.models.match import Match, MatchStatus

    async with _dbmod.async_session_factory() as session:
        from sqlalchemy import select
        stmt = (
            select(Match)
            .where(Match.league_id == local_league_id)
            .where(Match.status == MatchStatus.upcoming)
            .order_by(Match.match_time)
        )
        if not do_all:
            stmt = stmt.limit(limit)
        matches = (await session.execute(stmt)).scalars().all()

    print(f"[predict] 将为 {len(matches)} 场英超比赛生成 AI 预测（含联赛上下文）...")
    ok = 0
    for m in matches:
        try:
            await generate_single_match_predictions(m.id)
            ok += 1
            print(f"[predict] match {m.id} 完成")
        except Exception as e:
            print(f"[predict] match {m.id} 失败: {e!r}")
    print(f"[predict] 成功 {ok}/{len(matches)}")


# ── 入口 ────────────────────────────────────────────────

def main():
    _patch_engine_no_ssl()

    parser = argparse.ArgumentParser(description="英超数据同步脚本")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("discover", help="探查 Highlightly 上的英超候选")

    p_add = sub.add_parser("add", help="新增联赛并同步（默认英超 33973/2026）")
    p_add.add_argument("hl_id", type=int, nargs="?", default=33973,
                       help="Highlightly 联赛 ID（默认 33973=英超）")
    p_add.add_argument("season", type=int, nargs="?", default=2026,
                       help="赛季（默认 2026）")
    p_add.add_argument("--cn-name", default="英超")
    p_add.add_argument("--country", default="England")
    p_add.add_argument("--no-sync", action="store_true", help="只新增联赛，不同步比赛")
    p_add.add_argument("--h2h", action="store_true", help="同步后拉取 H2H")
    p_add.add_argument("--predict", action="store_true", help="同步后生成 AI 预测")

    p_sync = sub.add_parser("sync", help="同步已存在联赛的比赛")
    p_sync.add_argument("local_league_id", type=int)
    p_sync.add_argument("--h2h", action="store_true")
    p_sync.add_argument("--predict", action="store_true")

    p_setup = sub.add_parser("setup", help="一键探查并同步英格兰英超")
    p_setup.add_argument("--h2h", action="store_true")
    p_setup.add_argument("--predict", action="store_true")

    p_pred = sub.add_parser("predict", help="为某联赛 upcoming 比赛逐场生成 AI 预测")
    p_pred.add_argument("local_league_id", type=int)
    p_pred.add_argument("--limit", type=int, default=5, help="生成前 N 场（默认 5）")
    p_pred.add_argument("--all", action="store_true", help="为该联赛全部 upcoming 比赛生成")

    args = parser.parse_args()

    if args.cmd == "discover":
        asyncio.run(discover())
    elif args.cmd == "setup":
        asyncio.run(setup(do_h2h=args.h2h, do_predict=args.predict))
    elif args.cmd == "add":
        asyncio.run(add_league(
            hl_id=args.hl_id,
            season=args.season,
            cn_name=args.cn_name,
            country=args.country,
            do_sync=not args.no_sync,
            do_h2h=args.h2h,
            do_predict=args.predict,
        ))
    elif args.cmd == "sync":
        asyncio.run(sync_existing(args.local_league_id, args.h2h, args.predict))
    elif args.cmd == "predict":
        asyncio.run(predict_league(args.local_league_id, args.limit, args.all))


if __name__ == "__main__":
    main()
