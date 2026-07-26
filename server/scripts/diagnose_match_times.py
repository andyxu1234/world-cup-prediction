"""诊断脚本：查看 Highlightly 返回的比赛原始时间（不依赖本地数据库）

用法（在项目 virtualenv 中，需能访问外网）：
    cd server
    python scripts/diagnose_match_times.py

说明：
    - 欧冠 (UEFA Champions League) 的 Highlightly league_id = 2486, season = 2026
    - 直接调用 Highlightly /matches 与 /matches/{id}，绕开本地 MySQL（Windows 上 asyncmy 连不上）
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 让脚本能找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.core.highlightly import HighlightlyClient


HL_LEAGUE_ID = 2486   # UEFA Champions League
HL_SEASON = 2026


async def main():
    settings = get_settings()
    client = HighlightlyClient(
        api_key=settings.HIGHLIGHTLY_API_KEY,
        base_url=settings.HIGHLIGHTLY_BASE_URL,
    )

    print(f"=== Highlightly /matches (league_id={HL_LEAGUE_ID}, season={HL_SEASON}) ===")
    matches = await client.get_all_matches_by_league(league_id=HL_LEAGUE_ID, season=HL_SEASON)
    print(f"共返回 {len(matches)} 场\n")

    # 统计每个「时刻」出现的次数
    time_counter: Counter[str] = Counter()
    for m in matches:
        d = m.get("date")
        if d:
            # 取 UTC 时间的 HH:MM（Highlightly 返回的 date 多为 UTC，带 Z）
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                utc = dt.astimezone(timezone.utc)
                # 北京时间 = UTC + 8
                bj = utc.astimezone(timezone(offset=timedelta(hours=8)))
                time_counter[bj.strftime("%H:%M")] += 1
            except Exception:
                time_counter["(解析失败) " + str(d)[:19]] += 1

    print("--- 各比赛时间（北京时间 HH:MM）出现次数 ---")
    for t, c in sorted(time_counter.items()):
        print(f"  {t}: {c}")
    print()

    # 打印前 12 场的原始 date 字段
    print("--- 前 12 场原始 date 字段 ---")
    for m in matches[:12]:
        print(json.dumps({
            "id": m.get("id"),
            "date": m.get("date"),
            "round": m.get("round"),
            "home": m.get("homeTeam", {}).get("name"),
            "away": m.get("awayTeam", {}).get("name"),
        }, ensure_ascii=False))

    # 取一场看详情接口是否有更准确的时间
    if matches:
        sample_id = matches[0].get("id")
        print(f"\n=== Highlightly /matches/{sample_id} 详情接口 ===")
        detail = await client.get_match_by_id(sample_id)
        if detail:
            print(json.dumps({
                "id": detail.get("id"),
                "date": detail.get("date"),
                "round": detail.get("round"),
                "venue": detail.get("venue"),
                "home": detail.get("homeTeam", {}).get("name"),
                "away": detail.get("awayTeam", {}).get("name"),
                "state": detail.get("state"),
            }, ensure_ascii=False, indent=2))
        else:
            print("详情接口无返回")

    await client.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
