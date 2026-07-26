"""Polymarket FDV 事件同步

从 Polymarket Gamma API 按 tag_slug=fdv 拉取 Token Launch FDV 市场。
每个事件包含多个价格档次（如 $50M / $100M / $500M），
独立于通用市场（polymarket_standalone）和足球赛事市场（polymarket_events）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from loguru import logger
from sqlalchemy import select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.polymarket_standalone import PolymarketStandaloneMarket

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

MAX_EVENTS = 200  # 最大拉取事件数


def _resolve_proxy() -> Optional[str]:
    try:
        cfg = get_settings()
        proxy = getattr(cfg, "POLYMARKET_PROXY", "") or ""
    except Exception:
        proxy = ""
    if proxy:
        return proxy
    import os
    return os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or None


def _load_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            import json
            return json.loads(value) or []
        except Exception:
            return []
    return []


def _parse_iso_ts(value: str) -> float:
    if not value:
        return 0.0
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def _ts_naive(ts: float) -> Optional[datetime]:
    if not ts or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


async def fetch_fdv_events(
    client: httpx.AsyncClient,
    limit: int = 40,
) -> list[dict]:
    """从 Events API 拉取 FDV tag 事件

    Returns:
        每个事件格式:
        {
            "event_slug": str,
            "title": str,
            "markets": [
                {
                    "slug": str,
                    "question": str,
                    "condition_id": str,
                    "yes_token_id": str,
                    "no_token_id": str,
                    "yes_price": float,
                    "no_price": float,
                    "volume": float,
                    "liquidity": float,
                    "end_date": str,
                    "end_ts": float,
                    "outcome": str,  # price_tier 标识
                }
            ],
            "volume": float,
        }
    """
    all_events: list[dict] = []
    cursor: Optional[str] = None
    pages = 0

    while pages < 10:  # 最多翻10页
        params: dict[str, str] = {
            "limit": str(min(limit, 100)),
            "tag_slug": "fdv",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        }
        if cursor:
            params["cursor"] = cursor

        try:
            resp = await client.get(
                f"{GAMMA_API}/events/keyset",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(15),
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"FDV events fetch failed: {e}")
            break

        events = data.get("events", [])
        if not events:
            break

        for ev in events:
            title = ev.get("title", "") or ""
            slug = ev.get("slug", "") or ""
            markets_raw = ev.get("markets", []) or []
            # 构建市场列表
            parsed_markets = []
            for m in markets_raw:
                if not isinstance(m, dict):
                    continue
                prices = _load_json_list(m.get("outcomePrices"))
                if len(prices) < 2:
                    continue
                token_ids = _load_json_list(m.get("clobTokenIds"))
                outcomes = _load_json_list(m.get("outcomes"))
                yes_idx = next(
                    (i for i, n in enumerate(outcomes) if str(n).strip().lower() == "yes"), None
                )
                no_idx = next(
                    (i for i, n in enumerate(outcomes) if str(n).strip().lower() == "no"), None
                )
                try:
                    yes_price = float(prices[0])
                    no_price = float(prices[1])
                except (TypeError, ValueError):
                    continue

                end_date = str(m.get("endDate") or m.get("endDateIso") or "")
                parsed_markets.append({
                    "slug": str(m.get("slug") or ""),
                    "question": str(m.get("question") or ""),
                    "condition_id": str(m.get("conditionId") or ""),
                    "yes_token_id": str(token_ids[yes_idx]) if yes_idx is not None and yes_idx < len(token_ids) else None,
                    "no_token_id": str(token_ids[no_idx]) if no_idx is not None and no_idx < len(token_ids) else None,
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": float(m.get("volume") or 0),
                    "liquidity": float(m.get("liquidity") or 0),
                    "min_order_size": float(m.get("orderMinSize") or 0),
                    "end_date": end_date,
                    "end_ts": _parse_iso_ts(end_date),
                })

            if parsed_markets:
                vol = sum(mk["volume"] for mk in parsed_markets)
                all_events.append({
                    "event_slug": slug,
                    "title": title,
                    "markets": parsed_markets,
                    "volume": vol,
                })

        pages += 1
        cursor = data.get("next_cursor")
        if not cursor:
            break

    # 按成交量排序
    all_events.sort(key=lambda e: e["volume"], reverse=True)
    return all_events


async def sync_fdv_events() -> dict:
    """同步 FDV 事件到 polymarket_standalone_markets 表

    每个子市场（不同价格档次）存为一行。
    """
    logger.info("[FDV] 开始同步 FDV 事件...")

    proxy = _resolve_proxy()
    async with httpx.AsyncClient(proxy=proxy) if proxy else httpx.AsyncClient() as client:
        events = await fetch_fdv_events(client)

    logger.info(f"[FDV] 拉取完成: {len(events)} 个事件, "
                f"{sum(len(e['markets']) for e in events)} 个子市场")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    new_count = 0
    updated_count = 0
    eligible_count = 0

    async with async_session_factory() as session:
        for ev in events:
            for mk in ev["markets"]:
                if not mk["slug"]:
                    continue

                row = (
                    await session.execute(
                        select(PolymarketStandaloneMarket).where(
                            PolymarketStandaloneMarket.slug == mk["slug"]
                        )
                    )
                ).scalar_one_or_none()

                is_new = row is None
                if row is None:
                    row = PolymarketStandaloneMarket(slug=mk["slug"])
                    session.add(row)

                row.condition_id = mk.get("condition_id")
                row.question = mk.get("question")
                row.yes_token_id = mk.get("yes_token_id")
                row.no_token_id = mk.get("no_token_id")
                row.yes_price = mk.get("yes_price")
                row.no_price = mk.get("no_price")
                row.volume = mk.get("volume")
                row.liquidity = mk.get("liquidity")
                row.min_order_size = mk.get("min_order_size")
                row.end_date = mk.get("end_date")
                row.end_ts = mk.get("end_ts") if mk.get("end_ts", 0) > 0 else None
                row.event_slug = ev["event_slug"]
                row.category = f"FDV / {ev['title'][:40]}"
                row.last_synced_at = now

                # 判断 eligible
                no_price = mk.get("no_price")
                if no_price is not None and no_price <= 0.65:
                    row.is_eligible = True
                    row.no_entry_price = no_price
                else:
                    row.is_eligible = False
                    row.no_entry_price = None

                if is_new:
                    new_count += 1
                else:
                    updated_count += 1
                if row.is_eligible:
                    eligible_count += 1

        await session.commit()

    logger.info(
        f"[FDV] 同步完成: {new_count} 新建, {updated_count} 更新, "
        f"{eligible_count} 符合条件"
    )

    return {
        "events": len(events),
        "markets": new_count + updated_count,
        "new": new_count,
        "updated": updated_count,
        "eligible": eligible_count,
    }
