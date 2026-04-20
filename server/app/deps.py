from __future__ import annotations

from typing import Annotated
from fastapi import Depends
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
        league_id=settings.HIGHLIGHTLY_LEAGUE_ID,
        season=settings.HIGHLIGHTLY_SEASON,
    )


OfoxAIDep = Annotated[OfoxAIClient, Depends(get_ofoxai_client)]
HighlightlyDep = Annotated[HighlightlyClient, Depends(get_highlightly_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
