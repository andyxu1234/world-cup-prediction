from __future__ import annotations

from typing import Annotated, Optional
from fastapi import Depends, Request, Query, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.ofoxai import OfoxAIClient
from app.core.highlightly import HighlightlyClient
from app.config import get_settings, Settings

DBSession = Annotated[AsyncSession, Depends(get_db)]


def get_ofoxai_client(settings: Annotated[Settings, Depends(get_settings)]) -> OfoxAIClient:
    return OfoxAIClient(api_key=settings.OFOXAI_API_KEY, base_url=settings.OFOXAI_BASE_URL)


def get_highlightly_client(settings: Annotated[Settings, Depends(get_settings)]) -> HighlightlyClient:
    return HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )


OfoxAIDep = Annotated[OfoxAIClient, Depends(get_ofoxai_client)]
HighlightlyDep = Annotated[HighlightlyClient, Depends(get_highlightly_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_odds_token(
    request: Request,
    token: Optional[str] = Query(default=None),
    settings: SettingsDep = None,
) -> bool:
    """私密赔率页共享令牌闸（本地优先，公网部署时务必改 ODDS_VIEW_TOKEN 并加 IP 白名单）

    令牌可通过 `?token=xxx` 查询参数或 `X-Access-Token` 请求头传入。
    """
    expected = settings.ODDS_VIEW_TOKEN
    if not expected or expected == "odds-dev-local":
        logger.warning(
            "ODDS_VIEW_TOKEN 未配置或使用默认开发令牌，存在泄露风险；公网部署前请修改 .env"
        )
    provided = token or request.headers.get("X-Access-Token")
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing ODDS_VIEW_TOKEN")
    return True
