from __future__ import annotations

import ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 必须传 ssl.SSLContext 对象，不能传 dict：
# aiomysql 会把 connect_args["ssl"] 原样丢给 asyncio.create_connection，
# dict 会触发 "'dict' object has no attribute 'wrap_bio'"；
# asyncmy / pymysql 同样能正常接收 SSLContext，故统一用对象，跨驱动/跨平台一致。
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    # 取出连接前先发 SELECT 1 探活：若连接已被 MySQL/代理回收（2013 Lost connection），
    # 自动丢弃并新建，避免长耗时 AI 调用后复用到死连接。
    pool_pre_ping=True,
    connect_args={"ssl": _ssl_ctx},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取异步数据库 session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
