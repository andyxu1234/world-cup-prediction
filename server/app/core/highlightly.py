from __future__ import annotations

import asyncio
import httpx
from loguru import logger
from typing import Optional
from urllib.parse import urlparse


class HighlightlyAPIError(Exception):
    """Highlightly 接口调用失败（含状态码与响应体摘要），便于日志定位"""


class HighlightlyClient:
    """Highlightly Football API 客户端 — 获取赛程、比分、阵容、事件等数据

    多联赛改造后，league_id / season 不再在 __init__ 写死，
    而是由调用方在每次请求时显式传入（与 leagues 表联动）。

    通过 RapidAPI 代理访问时，必须带上 x-rapidapi-host 与 Content-Type 头，
    且路径需带 /football 前缀（默认 base_url 已包含）。
    """

    # 浏览器 UA：soccer.highlightly.net 前置 Cloudflare，会对 python-httpx 等脚本 UA
    # 返回 403 Error 1010 (Access denied)，必须伪装成浏览器 UA 才能正常拉取。
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://sport-highlights-api.p.rapidapi.com/football",
        user_agent: Optional[str] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        # RapidAPI 代理要求 x-rapidapi-host 与请求主机一致，并携带 Content-Type
        host = urlparse(self.base_url).netloc
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": host,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": user_agent or self.DEFAULT_UA,
            },
            timeout=30.0,
        )

    # ── 通用 GET（带重试 / 详细错误） ──────────────────────

    async def _request_json(
        self,
        path: str,
        params: Optional[dict] = None,
        *,
        retries: int = 3,
        retriable_statuses: tuple[int, ...] = (403, 429, 500, 502, 503, 504),
    ) -> tuple[Optional[dict], Optional[list]]:
        """发起 GET 并解析 JSON，对可重试状态码做指数退避重试。

        返回 (dict_or_list, None) 表示成功；对 404 返回 (None, None) 交由调用方判断。
        其余不可重试或耗尽重试的失败，抛出携带状态码与响应体的 HighlightlyAPIError。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                resp = await self.client.get(path, params=params)
                if resp.status_code == 404:
                    return None, None
                if resp.status_code in retriable_statuses:
                    last_exc = httpx.HTTPStatusError(
                        f"{resp.status_code} {resp.reason_phrase}",
                        request=resp.request,
                        response=resp,
                    )
                    if attempt < retries:
                        await asyncio.sleep(2 ** (attempt - 1))
                        continue
                    resp.raise_for_status()
                if resp.status_code >= 400:
                    resp.raise_for_status()
                data = resp.json()
                return data, None
            except httpx.HTTPStatusError as e:
                last_exc = e
                status = e.response.status_code if e.response is not None else "?"
                body = ""
                try:
                    body = e.response.text[:300] if e.response is not None else ""
                except Exception:  # noqa
                    pass
                if attempt < retries and status in retriable_statuses:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise HighlightlyAPIError(
                    f"HTTP {status} for {path}: {body}"
                ) from e
            except (httpx.RequestError, ValueError) as e:
                last_exc = e
                if attempt < retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise HighlightlyAPIError(f"{type(e).__name__} for {path}: {e}") from e
        # 理论上不会到这，保险起见
        raise HighlightlyAPIError(f"request failed after {retries} retries: {last_exc}")

    # ── Leagues ──────────────────────────────────────────────

    async def get_leagues(self, limit: int = 100, offset: int = 0) -> dict:
        """获取 Highlightly 支持的联赛列表"""
        params = {"limit": limit, "offset": offset}
        resp = await self.client.get("/leagues", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Matches ──────────────────────────────────────────────

    async def get_matches(
        self,
        league_id: int,
        season: int,
        date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """获取指定联赛某赛季的比赛列表，返回 {"data": [...], "pagination": {...}}"""
        params: dict = {
            "leagueId": league_id,
            "season": season,
            "limit": limit,
            "offset": offset,
        }
        if date:
            params["date"] = date

        resp = await self.client.get("/matches", params=params)
        resp.raise_for_status()
        data = resp.json()
        total = data.get("pagination", {}).get("totalCount", 0)
        logger.info(f"Highlightly matches: {len(data.get('data', []))} returned, total={total}")
        return data

    async def get_match_by_id(self, match_id: int) -> Optional[dict]:
        """根据 ID 获取单场比赛详情（含 events, statistics, venue, predictions）"""
        resp = await self.client.get(f"/matches/{match_id}")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return None

    async def get_all_matches_by_league(self, league_id: int, season: int) -> list[dict]:
        """获取指定联赛某赛季的所有比赛（自动翻页）"""
        all_matches = []
        offset = 0
        limit = 100
        while True:
            data = await self.get_matches(league_id=league_id, season=season, limit=limit, offset=offset)
            matches = data.get("data", [])
            all_matches.extend(matches)
            pagination = data.get("pagination", {})
            total = pagination.get("totalCount", 0)
            offset += limit
            if offset >= total or not matches:
                break
        return all_matches

    # ── Standings ────────────────────────────────────────────

    async def get_standings(
        self,
        league_id: int,
        season: int,
    ) -> dict:
        """获取积分榜/小组排名"""
        params = {
            "leagueId": league_id,
            "season": season,
        }
        data, _ = await self._request_json("/standings", params=params)
        return data or {}

    # ── Highlights ───────────────────────────────────────────

    async def get_highlights(
        self,
        league_id: Optional[int] = None,
        match_id: Optional[int] = None,
        date: Optional[str] = None,
        limit: int = 40,
        offset: int = 0,
    ) -> dict:
        """获取比赛集锦（可按 match_id 或 league_id 过滤）"""
        params: dict = {"limit": limit, "offset": offset}
        if league_id:
            params["leagueId"] = league_id
        if match_id:
            params["matchId"] = match_id
        if date:
            params["date"] = date

        resp = await self.client.get("/highlights", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Head to Head ────────────────────────────────────────

    async def get_head_to_head(self, team_id_one: int, team_id_two: int) -> list[dict]:
        """获取两队历史交锋（最近10场）"""
        resp = await self.client.get(
            "/head-2-head",
            params={"teamIdOne": team_id_one, "teamIdTwo": team_id_two},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Lineups ─────────────────────────────────────────────

    async def get_lineups(self, match_id: int) -> Optional[dict]:
        """获取比赛首发阵容"""
        resp = await self.client.get(f"/lineups/{match_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # ── Events ──────────────────────────────────────────────

    async def get_events(self, match_id: int) -> list[dict]:
        """获取比赛实时事件（进球、红黄牌、换人等）"""
        resp = await self.client.get(f"/events/{match_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Statistics ───────────────────────────────────────────

    async def get_statistics(self, match_id: int) -> list[dict]:
        """获取比赛统计数据"""
        resp = await self.client.get(f"/statistics/{match_id}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    # ── Box Score ──────────────────────────────────────────

    async def get_box_score(self, match_id: int) -> list[dict]:
        """获取单场比赛的盒子分（逐球员详细数据：进球/助攻/牌/射门等）

        Args:
            match_id: Highlightly 比赛 ID（非本地 ID）

        Returns:
            list[dict]: 按球队分组的球员数据，结构为
            [{"team": {...}, "players": [{"id", "name", "statistics": [{...}]}, ...]}]
            比赛暂无 box-score 时返回空列表。
        """
        data, _ = await self._request_json(f"/box-score/{match_id}")
        if data is None:
            return []
        # 部分响应用 {"data": [...]} 包裹
        if isinstance(data, dict):
            return data.get("data", [])
        return data or []

    # ── Teams ───────────────────────────────────────────────

    async def get_teams(
        self,
        name: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict:
        """获取球队列表（含 logo 字段）"""
        params: dict = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name
        resp = await self.client.get("/teams", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_team_by_id(self, team_id: int) -> Optional[dict]:
        """根据 Highlightly team id 获取球队详情（含 logo）"""
        resp = await self.client.get(f"/teams/{team_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return data if isinstance(data, dict) else None

    async def get_team_statistics(
        self, team_id: int, from_date: str, timezone: str = "Etc/UTC"
    ) -> list[dict]:
        """获取球队赛季统计（胜平负、进球失球、主客场拆分）"""
        resp = await self.client.get(
            f"/teams/statistics/{team_id}",
            params={"fromDate": from_date, "timezone": timezone},
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    # ── Last Five Games ────────────────────────────────────

    async def get_last_five_games(self, team_id: int) -> list[dict]:
        """获取球队最近5场已完赛结果"""
        resp = await self.client.get(
            "/last-five-games", params={"teamId": team_id}
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    # ── Players ────────────────────────────────────────────

    async def get_players(
        self,
        name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """获取球员列表（仅支持 name/limit/offset 过滤，无 leagueId/teamId）"""
        params: dict = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name
        resp = await self.client.get("/players", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_player_by_id(self, player_id: int) -> Optional[dict]:
        """根据 Highlightly player id 获取球员主数据（响应为数组，取首个元素）"""
        resp = await self.client.get(f"/players/{player_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return data if isinstance(data, dict) else None

    async def get_player_statistics(self, player_id: int) -> list[dict]:
        """获取球员赛季统计（按联赛拆分；联赛名匹配脆弱，仅供补充参考）"""
        resp = await self.client.get(f"/players/{player_id}/statistics")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    # ── Countries ────────────────────────────────────────────

    async def get_countries(self, name: Optional[str] = None) -> list[dict]:
        """获取国家列表"""
        params = {}
        if name:
            params["name"] = name
        resp = await self.client.get("/countries", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Rate Limit Info ──────────────────────────────────────

    async def get_rate_limit_info(self) -> dict:
        """获取当前配额信息"""
        resp = await self.client.get("/countries")
        return {
            "limit": resp.headers.get("x-ratelimit-requests-limit"),
            "remaining": resp.headers.get("x-ratelimit-requests-remaining"),
        }

    # ── Lifecycle ────────────────────────────────────────────

    async def close(self):
        await self.client.aclose()
