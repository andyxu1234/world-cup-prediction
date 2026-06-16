"""统一缓存管理

单 Worker 模式下，所有缓存共享同一进程内存。
- 只读数据：5~10 分钟 TTL
- 用户数据：30 秒 TTL + 写后失效
- 趣味文案：1 小时 TTL
"""

from __future__ import annotations

import asyncio
import time
from cachetools import TTLCache
from functools import wraps
from loguru import logger
from typing import Any, Callable, Awaitable


# ──────────────────────── Cache 实例 ────────────────────────

# 只读缓存（数据变更频率低，5~10 分钟 TTL）
stats_cache = TTLCache(maxsize=10, ttl=300)          # 首页统计
matches_cache = TTLCache(maxsize=50, ttl=300)         # 比赛列表
match_detail_cache = TTLCache(maxsize=200, ttl=300)   # 比赛详情
prediction_cache = TTLCache(maxsize=200, ttl=600)     # AI 预测
compare_cache = TTLCache(maxsize=200, ttl=600)        # 预测对比
face_slap_cache = TTLCache(maxsize=30, ttl=600)       # 打脸合集
leaderboard_cache = TTLCache(maxsize=50, ttl=300)     # 排行榜
standings_cache = TTLCache(maxsize=20, ttl=300)       # 小组积分榜
long_term_cache = TTLCache(maxsize=10, ttl=600)       # 长期预测
fun_fact_cache = TTLCache(maxsize=100, ttl=3600)      # 趣味文案（1h，调用 DeepSeek 成本高）

# 用户相关缓存（短 TTL，写后失效）
user_profile_cache = TTLCache(maxsize=500, ttl=60)    # 用户信息
user_votes_cache = TTLCache(maxsize=500, ttl=60)      # 投票历史
user_vote_cache = TTLCache(maxsize=1000, ttl=60)      # 单场投票状态


# ──────────────────────── 缓存统计 ────────────────────────

_hits = 0
_misses = 0
_last_log_time = 0.0


def _record_hit():
    global _hits
    _hits += 1


def _record_miss():
    global _misses
    _misses += 1


def maybe_log_stats(interval: int = 60):
    """每隔 interval 秒打印一次缓存统计"""
    global _last_log_time
    now = time.time()
    if now - _last_log_time < interval:
        return
    _last_log_time = now
    total = _hits + _misses
    rate = round(_hits / total * 100, 1) if total > 0 else 0
    logger.info(
        f"[Cache] hits={_hits} misses={_misses} rate={rate}% | "
        f"sizes: stats={len(stats_cache)} matches={len(matches_cache)} "
        f"match_detail={len(match_detail_cache)} prediction={len(prediction_cache)} "
        f"compare={len(compare_cache)} face_slap={len(face_slap_cache)} "
        f"leaderboard={len(leaderboard_cache)} long_term={len(long_term_cache)} "
        f"fun_fact={len(fun_fact_cache)} "
        f"user_profile={len(user_profile_cache)} user_votes={len(user_votes_cache)} "
        f"user_vote={len(user_vote_cache)}"
    )


# ──────────────────────── 核心方法 ────────────────────────

async def get_or_set(cache: TTLCache, key: str, fetch_fn: Callable[[], Awaitable[Any]]) -> Any:
    """从缓存读取，未命中则执行 fetch_fn 并写入缓存"""
    if key in cache:
        _record_hit()
        maybe_log_stats()
        return cache[key]

    _record_miss()
    result = await fetch_fn()
    cache[key] = result
    maybe_log_stats()
    return result


def invalidate(cache: TTLCache, key: str):
    """移除单个缓存 key"""
    cache.pop(key, None)


def invalidate_user(user_id: int):
    """用户写操作后，清除该用户相关的缓存"""
    user_profile_cache.pop(f"profile:{user_id}", None)
    user_votes_cache.pop(f"votes:{user_id}", None)
    # 单场投票 key 包含 match_id，难以精确清除，直接清空整个 cache（短 TTL，代价低）
    user_vote_cache.clear()
    # 用户投票影响排行榜和首页统计
    leaderboard_cache.clear()
    stats_cache.pop("home_stats", None)


def clear_all_caches():
    """清空所有缓存"""
    for c in [
        stats_cache, matches_cache, match_detail_cache, prediction_cache,
        compare_cache, face_slap_cache, leaderboard_cache, standings_cache,
        long_term_cache, fun_fact_cache, user_profile_cache, user_votes_cache,
        user_vote_cache,
    ]:
        c.clear()
    logger.info("[Cache] All caches cleared")


def get_cache_stats() -> dict:
    """返回缓存统计信息（供监控接口使用）"""
    total = _hits + _misses
    return {
        "hits": _hits,
        "misses": _misses,
        "hit_rate": round(_hits / total * 100, 1) if total > 0 else 0,
        "sizes": {
            "stats": len(stats_cache),
            "matches": len(matches_cache),
            "match_detail": len(match_detail_cache),
            "prediction": len(prediction_cache),
            "compare": len(compare_cache),
            "face_slap": len(face_slap_cache),
            "leaderboard": len(leaderboard_cache),
            "standings": len(standings_cache),
            "long_term": len(long_term_cache),
            "fun_fact": len(fun_fact_cache),
            "user_profile": len(user_profile_cache),
            "user_votes": len(user_votes_cache),
            "user_vote": len(user_vote_cache),
        },
    }


# ──────────────────────── 装饰器（兼容 leaderboard_calc.py） ────────────────────────

def cached(cache_obj: TTLCache, key_fn=None):
    """通用缓存装饰器（用于 service 层函数，如 leaderboard_calc）"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs) if key_fn else f"{func.__name__}:{args}:{kwargs}"
            if key in cache_obj:
                _record_hit()
                return cache_obj[key]
            result = await func(*args, **kwargs)
            cache_obj[key] = result
            _record_miss()
            return result
        return wrapper
    return decorator
