from __future__ import annotations

import httpx
from loguru import logger


class APIFootballClient:
    """API-Football 客户端 — 获取赛程、比分、历史交锋数据"""

    def __init__(self, api_key: str, base_url: str = "https://v3.football.api-sports.io"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-apisports-key": api_key,
            },
            timeout=30.0,
        )

    async def get_fixtures(
        self,
        league: int = 1,       # 1 = FIFA World Cup
        season: int = 2026,
        date: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        round: str | None = None,
    ) -> tuple[list[dict], dict]:
        """获取比赛赛程，返回 (fixtures, errors)"""
        params: dict = {"league": league, "season": season}
        if date:
            params["date"] = date
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if round:
            params["round"] = round

        resp = await self.client.get("/fixtures", params=params)
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors", {})
        results = data.get("results", 0)
        logger.info(f"API-Football fixtures: {results} results, errors: {errors or 'none'}")
        return data.get("response", []), errors

    async def get_fixture_by_id(self, fixture_id: int) -> dict | None:
        """根据 ID 获取单场比赛"""
        resp = await self.client.get("/fixtures", params={"id": fixture_id})
        resp.raise_for_status()
        data = resp.json()
        results = data.get("response", [])
        return results[0] if results else None

    async def get_head_to_head(
        self,
        team1_id: int,
        team2_id: int,
        last: int = 5,
    ) -> list[dict]:
        """获取两队历史交锋"""
        resp = await self.client.get(
            "/fixtures/headtohead",
            params={"h2h": f"{team1_id}-{team2_id}", "last": last},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", [])

    async def get_teams(self, league: int = 1, season: int = 2026) -> list[dict]:
        """获取参赛球队"""
        resp = await self.client.get("/teams", params={"league": league, "season": season})
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", [])

    async def get_standings(self, league: int = 1, season: int = 2026) -> list[dict]:
        """获取积分榜"""
        resp = await self.client.get("/standings", params={"league": league, "season": season})
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", [])

    async def close(self):
        await self.client.aclose()
