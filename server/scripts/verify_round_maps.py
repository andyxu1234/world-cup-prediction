"""查看 cn_mappings 表中 round 类别的翻译（Windows 下去掉 SSL）"""
from __future__ import annotations

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.database as _dbmod
from app.config import get_settings
from sqlalchemy import select, text


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
        # 先看看表结构
        rows = (await session.execute(
            select(text("category, `key`, cn_value, is_series"))
            .select_from(text("cn_mappings"))
            .where(text("category = 'round'"))
            .order_by(text("`key`"))
        )).all()
        print(f"round 映射共 {len(rows)} 条：")
        for r in rows:
            print(f"  key={r.key!r:30} cn_value={r.cn_value!r:20} is_series={r.is_series}")


if __name__ == "__main__":
    _patch_engine_no_ssl()
    asyncio.run(main())
