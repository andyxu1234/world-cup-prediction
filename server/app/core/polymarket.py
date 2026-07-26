"""Polymarket Gamma API 客户端（只读）— 拉取未来 N 天的足球赛事及其"胜负平"市场。

只做一件事：按 series（联赛）拉取 closed=false 的赛事，
过滤出未来 days_ahead 天内开赛的比赛，并从每个赛事的 markets 中
提取 moneyline 3-way（胜/平/负）三条腿的隐含概率。

不做本地 matches 匹配（后续单独做），不涉及任何交易/下单。
仅读公开 Gamma API，无需 API Key。
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from loguru import logger

from app.config import get_settings

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _resolve_proxy() -> Optional[str]:
    """解析 Polymarket 出网代理：config.POLYMARKET_PROXY > HTTPS_PROXY > HTTP_PROXY。

    返回代理 URL 字符串；未配置则返回 None（直连）。
    """
    try:
        cfg = get_settings()
        proxy = getattr(cfg, "POLYMARKET_PROXY", "") or ""
    except Exception:
        proxy = ""
    if proxy:
        return proxy
    return os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or None


# ── 基础解析工具 ─────────────────────────────────────────────


def _load_json_list(value: Any) -> list:
    """Gamma 的 outcomes/outcomePrices 等字段是字符串化 JSON，统一转 list。"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value) or []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _load_json_dict(value: Any) -> dict:
    """marketMetadata 可能是 dict 也可能是字符串化 JSON。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            data = json.loads(value)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _parse_iso_ts(value: Any) -> float:
    """ISO8601 字符串 -> UTC 秒；解析失败返回 0。"""
    if not value or not isinstance(value, str):
        return 0.0
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _parse_teams_from_title(title: str) -> tuple[str, str]:
    """从 'TeamA vs. TeamB' 切出主客队名；无分隔符则返回 (title, '')。"""
    for sep in (" vs. ", " vs ", " v ", " v. "):
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return title.strip(), ""


def _extract_home_away(ev: dict) -> tuple[str, str]:
    """优先用事件的 teams 数组（带 ordering: home/away），退化为标题解析。"""
    home, away = "", ""
    for t in ev.get("teams") or []:
        if not isinstance(t, dict):
            continue
        ordering = str(t.get("ordering") or "").lower()
        name = str(t.get("name") or "").strip()
        if ordering == "home" and name:
            home = name
        elif ordering == "away" and name:
            away = name
    if home and away:
        return home, away
    return _parse_teams_from_title(str(ev.get("title") or ""))


def _extract_game_start_ts(ev: dict) -> float:
    """比赛开球时间（UTC 秒）。

    优先级：markets[].gameStartTime > event.startTime > event.endDate。
    注意 event.startDate 是市场上架时间，不是比赛时间，不能用。
    """
    for m in ev.get("markets") or []:
        ts = _parse_iso_ts(m.get("gameStartTime"))
        if ts > 0:
            return ts
    for key in ("startTime", "endDate"):
        ts = _parse_iso_ts(ev.get(key))
        if ts > 0:
            return ts
    return 0.0


def _yes_price(market: dict) -> Optional[float]:
    """从 outcomes/outcomePrices 中取 'Yes' 的价格（即该结果的隐含概率）。"""
    outcomes = _load_json_list(market.get("outcomes"))
    prices = _load_json_list(market.get("outcomePrices"))
    if not outcomes or not prices or len(outcomes) != len(prices):
        return None
    idx = 0
    for i, name in enumerate(outcomes):
        if str(name).strip().lower() == "yes":
            idx = i
            break
    try:
        return float(prices[idx])
    except (TypeError, ValueError, IndexError):
        return None


def extract_moneyline_markets(ev: dict, home: str, away: str) -> list[dict]:
    """从事件的 markets 中提取胜负平三条腿（moneyline 3-way）。

    返回 [{pm_market_id, condition_id, question, outcome(home/draw/away),
           outcome_team, price, volume, liquidity}]，最多 3 条。
    识别策略（依次退化）：
      1) marketMetadata.opticOddsSelectionLine == home/draw/away
      2) question 文本含 draw / 主队名 / 客队名
      3) groupItemThreshold: 0=home, 1=draw, 2=away
    """
    legs: dict[str, dict] = {}
    for m in ev.get("markets") or []:
        if not isinstance(m, dict):
            continue
        if str(m.get("sportsMarketType") or "").strip().lower() != "moneyline":
            continue

        md = _load_json_dict(m.get("marketMetadata"))
        line = str(md.get("opticOddsSelectionLine") or "").strip().lower()
        outcome: Optional[str] = line if line in ("home", "draw", "away") else None

        if outcome is None:
            q = str(m.get("question") or "").lower()
            if "draw" in q:
                outcome = "draw"
            elif home and home.lower() in q:
                outcome = "home"
            elif away and away.lower() in q:
                outcome = "away"

        if outcome is None:
            git = str(m.get("groupItemThreshold") or "").strip()
            outcome = {"0": "home", "1": "draw", "2": "away"}.get(git)

        if outcome is None:
            continue

        price = _yes_price(m)
        # clobTokenIds 与 outcomes 下标一一对应：取 Yes / No 两侧 token（下单用）
        _outcomes = _load_json_list(m.get("outcomes"))
        _clobs = _load_json_list(m.get("clobTokenIds"))
        _positions = _load_json_list(m.get("positionIds"))
        _yes_idx = next(
            (i for i, n in enumerate(_outcomes) if str(n).strip().lower() == "yes"), None
        )
        _no_idx = next(
            (i for i, n in enumerate(_outcomes) if str(n).strip().lower() == "no"), None
        )
        clob_yes = _clobs[_yes_idx] if (_yes_idx is not None and _yes_idx < len(_clobs)) else None
        clob_no = _clobs[_no_idx] if (_no_idx is not None and _no_idx < len(_clobs)) else None
        pos_yes = _positions[_yes_idx] if (_yes_idx is not None and _yes_idx < len(_positions)) else None
        pos_no = _positions[_no_idx] if (_no_idx is not None and _no_idx < len(_positions)) else None
        leg = {
            "pm_market_id": str(m.get("id") or ""),
            "condition_id": str(m.get("conditionId") or ""),
            "question": str(m.get("question") or ""),
            "clob_token_id_yes": str(clob_yes) if clob_yes else None,
            "clob_token_id_no": str(clob_no) if clob_no else None,
            "position_id_yes": str(pos_yes) if pos_yes else None,
            "position_id_no": str(pos_no) if pos_no else None,
            "outcome": outcome,
            "outcome_team": home if outcome == "home" else (away if outcome == "away" else None),
            "price": price,
            "volume": float(m.get("volume") or 0),
            "liquidity": float(m.get("liquidity") or 0),
        }
        # 同一 outcome 出现多个市场时保留成交量更大的那个
        old = legs.get(outcome)
        if old is None or leg["volume"] > old["volume"]:
            legs[outcome] = leg
    return list(legs.values())


# ── 拉取 ─────────────────────────────────────────────────────


async def _fetch_event_page(
    session: httpx.AsyncClient,
    series_id: str,
    cursor: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    # closed=false：只要未收盘（未开赛/进行中）的赛事，历史赛事不拉。
    params: dict[str, str] = {
        "locale": "en",
        "series_id": series_id,
        "closed": "false",
        "limit": "500",
    }
    # endDate 服务端按比赛时间(事件 endDate)上限过滤，把拉取范围收窄到目标窗口，
    # 避免翻完整个联赛的历史事件（曾出现单 series 7 万+ 事件翻 700+ 页）。
    if end_date:
        params["endDate"] = end_date
    if cursor:
        params["cursor"] = cursor
    # 注意：httpx 的 .get() 是协程需 await；.json() 是同步方法不能 await。
    resp = await session.get(
        f"{GAMMA_API}/events/keyset",
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(15),
    )
    resp.raise_for_status()
    return resp.json()


async def fetch_upcoming_moneyline(
    series_id: str,
    series_name: Optional[str] = None,
    days_ahead: int = 7,
    session: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """拉取某联赛未来 days_ahead 天内的比赛 + 胜负平市场。

    每个元素:
        {
            "event_id": str,           # Polymarket 事件 id
            "slug": str,               # 稳定唯一
            "title": "TeamA vs. TeamB",
            "series_id": str,          # 联赛 series_id
            "series_name": str,        # 联赛名
            "home_team": str,
            "away_team": str,
            "game_start_ts": float,    # UTC 秒
            "markets": [ {pm_market_id, condition_id, question,
                          outcome, outcome_team, price, volume, liquidity} ],
        }
    只保留解析出至少 1 条胜负平腿的赛事。
    """
    all_events: list[dict] = []
    cursor: Optional[str] = None
    own = session is None
    # 提前算好时间窗口，用于服务端 endDate 上限过滤（按比赛时间收窄拉取范围）
    now = time.time()
    hi_iso = (
        datetime.fromtimestamp(now + days_ahead * 86400, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    max_pages = int(getattr(get_settings(), "POLYMARKET_MAX_PAGES", 50))
    if own:
        proxy = _resolve_proxy()
        session = httpx.AsyncClient(proxy=proxy) if proxy else httpx.AsyncClient()
    try:
        page = 0
        while True:
            page += 1
            if page > max_pages:
                logger.warning(
                    f"[Polymarket] series {series_id} 翻页超过 {max_pages} 页，强制停止"
                )
                break
            data = await _fetch_event_page(session, series_id, cursor, end_date=hi_iso)
            events = data.get("events", [])
            if not events:
                break
            all_events.extend(events)
            logger.info(
                f"[Polymarket]   {series_name or series_id} 第 {page} 页，"
                f"本页 {len(events)} 事件，累计 {len(all_events)}"
            )
            cursor = data.get("next_cursor")
            if not cursor:
                break
    except Exception as exc:
        logger.warning(f"polymarket series {series_id} fetch failed: {exc}")
        return []
    finally:
        if own:
            await session.aclose()

    # 窗口：[now - 2h, now + days_ahead 天]；-2h 容忍刚开球还没收盘的场次
    lo, hi = now - 2 * 3600, now + days_ahead * 86400

    results: list[dict] = []
    seen_slugs: set[str] = set()
    for ev in all_events:
        slug = str(ev.get("slug") or "")
        if not slug or slug in seen_slugs:
            continue
        start_ts = _extract_game_start_ts(ev)
        if start_ts <= 0 or not (lo <= start_ts <= hi):
            continue
        home, away = _extract_home_away(ev)
        if not home or not away:
            continue
        markets = extract_moneyline_markets(ev, home, away)
        if not markets:
            continue
        seen_slugs.add(slug)
        results.append(
            {
                "event_id": str(ev.get("id") or ""),
                "slug": slug,
                "title": str(ev.get("title") or f"{home} vs. {away}"),
                "series_id": str(series_id),
                "series_name": series_name or "",
                "home_team": home,
                "away_team": away,
                "game_start_ts": start_ts,
                "markets": markets,
            }
        )

    results.sort(key=lambda m: m["game_start_ts"])
    return results
