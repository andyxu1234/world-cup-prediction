from __future__ import annotations

import httpx
from loguru import logger
from typing import Optional


class HighlightlyClient:
    """Highlightly Football API 客户端 — 获取赛程、比分、阵容、事件等数据"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://soccer.highlightly.net",
        league_id: int = 1635,
        season: int = 2026,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.league_id = league_id
        self.season = season
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"x-rapidapi-key": api_key},
            timeout=30.0,
        )

    # ── Matches ──────────────────────────────────────────────

    async def get_matches(
        self,
        date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """获取比赛列表，返回 {"data": [...], "pagination": {...}}"""
        params: dict = {
            "leagueId": league_id or self.league_id,
            "season": season or self.season,
            "limit": limit,
            "offset": offset,
        }
        if date:
            params["date"] = date
            # date 查询时可以不带 leagueId，但保留以过滤世界杯

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

    async def get_matches_by_date(self, date: str) -> list[dict]:
        """获取指定日期的世界杯比赛"""
        data = await self.get_matches(date=date)
        return data.get("data", [])

    async def get_all_world_cup_matches(self) -> list[dict]:
        """获取世界杯所有比赛（自动翻页）"""
        all_matches = []
        offset = 0
        limit = 100
        while True:
            data = await self.get_matches(limit=limit, offset=offset)
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
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> dict:
        """获取积分榜/小组排名"""
        params = {
            "leagueId": league_id or self.league_id,
            "season": season or self.season,
        }
        resp = await self.client.get("/standings", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Highlights ───────────────────────────────────────────

    async def get_highlights(
        self,
        league_id: Optional[int] = None,
        match_id: Optional[int] = None,
        date: Optional[str] = None,
        limit: int = 40,
        offset: int = 0,
    ) -> dict:
        """获取比赛集锦"""
        params: dict = {"limit": limit, "offset": offset}
        if league_id or self.league_id:
            params["leagueId"] = league_id or self.league_id
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
