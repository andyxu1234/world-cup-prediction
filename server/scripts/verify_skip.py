"""诊断：同一场比赛重跑时，已成功的 AI 预测为何没有被跳过。

对比：
  - 该比赛在 predictions 表中已存的 model_id 列表
  - 当前 ai_models 表中活跃模型的 id 列表
若两者对不上（例如 ai_models 被重新灌过、id 变了），skip 判断
`model_info["id"] in existing_model_ids` 永远为 False，就会重复跑。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import app.database as _dbmod  # noqa: E402
from app.config import get_settings  # noqa: E402

if sys.platform == "win32":
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    s = get_settings()
    url = (
        f"mysql+asyncmy://{s.DB_USER}:{s.DB_PASSWORD}"
        f"@{s.DB_HOST}:{s.DB_PORT}/{s.DB_NAME}"
    )
    engine = create_async_engine(url, pool_recycle=3600, pool_size=5, max_overflow=10)
    _dbmod.engine = engine
    _dbmod.async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

from sqlalchemy import select  # noqa: E402
from app.models.prediction import Prediction  # noqa: E402
from app.models.ai_model import AIModel  # noqa: E402


async def main(match_id: int):
    async with _dbmod.async_session_factory() as session:
        # 已存预测的 model_id
        pred_rows = (
            await session.execute(
                select(Prediction.model_id).where(Prediction.match_id == match_id)
            )
        ).all()
        existing = [r[0] for r in pred_rows]

        # 当前活跃模型
        model_rows = (
            await session.execute(select(AIModel).where(AIModel.is_active == True))
        ).scalars().all()
        active = [{"id": m.id, "name": m.name, "model_id": m.model_id} for m in model_rows]

    print(f"比赛 match_id={match_id}")
    print(f"\n[predictions 已存] model_id 列表 ({len(existing)}): {existing}")
    print("\n[ai_models 当前活跃] id / name / model_id:")
    for m in active:
        mark = "  <- 在已存列表中" if m["id"] in existing else "  <- 不在已存列表(会被重跑!)"
        print(f"  id={m['id']:>3}  {m['name']:<16} {m['model_id']:<28}{mark}")

    active_ids = {m["id"] for m in active}
    would_skip = [mid for mid in existing if mid in active_ids]
    would_rerun = [mid for mid in active_ids if mid not in existing]
    print(f"\n会被跳过: {len(would_skip)} 个")
    print(f"会被重跑: {len(would_rerun)} 个 (active 中不在已存列表的 id: {would_rerun})")

    # 已存但找不到对应活跃模型的（脏数据）
    orphan = [mid for mid in existing if mid not in active_ids]
    if orphan:
        print(f"\n⚠️ 已存预测里存在找不到活跃模型的 model_id（可能是 ai_models 被重灌导致 id 漂移）: {orphan}")


if __name__ == "__main__":
    mid = int(sys.argv[1]) if len(sys.argv) > 1 else 2728
    asyncio.run(main(mid))
