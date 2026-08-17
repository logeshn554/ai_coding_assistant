"""Redis-backed caching decorator with in-memory fallback."""
from __future__ import annotations

import functools
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from .state import redis_client

logger = logging.getLogger("loopix.cache")

F = TypeVar("F", bound=Callable[..., Any])


def cached(ttl: int = 300) -> Callable[[F], F]:
    """Decorator that caches the return value of an async function in Redis.

    The cache key is built from the function name and all keyword arguments.
    Non-serialisable values are safely skipped.

    Args:
        ttl: Cache time-to-live in seconds (default 5 minutes).
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build a deterministic cache key (skip ``self`` / ``cls`` args)
            serialisable = {
                k: v for k, v in kwargs.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }
            key = f"cache:{func.__module__}.{func.__qualname__}:{json.dumps(serialisable, sort_keys=True, default=str)}"

            # Try Redis first
            try:
                cached_raw = await redis_client.get(key)
                if cached_raw is not None:
                    return json.loads(cached_raw)
            except Exception as exc:
                logger.debug("Cache miss (Redis error) for %s: %s", key, exc)

            # Cache miss — execute function
            result = await func(*args, **kwargs)

            # Store result
            try:
                await redis_client.set(key, json.dumps(result, default=str), ex=ttl)
            except Exception as exc:
                logger.debug("Cache store failed for %s: %s", key, exc)

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


async def invalidate_pattern(pattern: str) -> int:
    """Delete all Redis keys matching *pattern*.

    Returns the number of keys deleted (best-effort under fallback).
    """
    try:
        keys = []
        cursor = 0
        while True:
            cursor, batch = await redis_client.client.scan(cursor, match=pattern, count=100)
            keys.extend(batch)
            if cursor == 0:
                break
        if keys:
            return await redis_client.delete(*keys)
        return 0
    except Exception as exc:
        logger.warning("Failed to invalidate cache pattern %s: %s", pattern, exc)
        return 0
