"""验证欧冠比赛时间在重同步后是否已修正（Windows 下去掉 SSL 以连接）"""
from __future__ import annotations

import sys
import asyncio
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.database as _dbmod
from app.config import get_settings
from sqlalchemy import select, func
from app.models.match import Match


def _patch_engine_no_ssl():
    if sys.platform != "win32":
        return
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    s = get_settings()
    url = f"mysql+asyncmy://{s.DB_USER}:{s.DB_PASSWORD}@{s.DB_HOST}:{s.DB_PORT}/{s.DB_NAME}"
    engine = create_async_engine(url, pool_recycle=3600, pool_size=5, max_overflow=10)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    _dbmod.engine = engine
    _dbmod.async_session_factory = factory


async def main():
    async with _dbmod.async_session_factory() as session:
        rows = (await session.execute(
            select(Match.match_time, func.count(Match.id))
            .where(Match.league_id == 7)
            .group_by(Match.match_time)
            .order_by(Match.match_time)
        )).all()
        print(f"欧冠(league_id=7) 共 {sum(c for _, c in rows)} 场，时间分布：")
        for mt, c in rows:
            print(f"  {mt} : {c}")


if __name__ == "__main__":
    _patch_engine_no_ssl()
    asyncio.run(main())
