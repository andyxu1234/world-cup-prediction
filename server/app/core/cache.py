from cachetools import TTLCache
from functools import wraps
from loguru import logger


# 比赛列表缓存 5 分钟
match_cache = TTLCache(maxsize=100, ttl=300)
# 预测结果缓存 10 分钟
prediction_cache = TTLCache(maxsize=500, ttl=600)
# 排行榜缓存 5 分钟
leaderboard_cache = TTLCache(maxsize=20, ttl=300)
# 打脸合集缓存 10 分钟
face_slap_cache = TTLCache(maxsize=10, ttl=600)


def cached(cache_obj: TTLCache, key_fn=None):
    """通用缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs) if key_fn else f"{func.__name__}:{args}:{kwargs}"
            if key in cache_obj:
                logger.debug(f"Cache hit: {key}")
                return cache_obj[key]
            result = await func(*args, **kwargs)
            cache_obj[key] = result
            return result
        return wrapper
    return decorator
