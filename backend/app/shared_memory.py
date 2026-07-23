"""Inter-agent shared memory via Redis hash (in-memory fallback).

Key format: ``{run_id}:shared_memory`` as a Redis HASH.
Never writes to disk — no shared_memory.txt.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .state import redis_client

logger = logging.getLogger("devpilot.shared_memory")

# Process-local fallback when Redis hash ops are unavailable.
_MEMORY: dict[str, dict[str, str]] = {}


def _hash_key(run_id: str) -> str:
    """Build the Redis hash key for a run."""
    return f"{run_id}:shared_memory"


async def sm_set(run_id: str, key: str, value: Any) -> None:
    """Set a single field in the shared memory hash for ``run_id``.

    Args:
        run_id: Orchestration / workspace run identifier.
        key: Field name.
        value: JSON-serializable value.
    """
    serialized = value if isinstance(value, str) else json.dumps(value)
    redis_key = _hash_key(run_id)
    try:
        if hasattr(redis_client, "hset"):
            await redis_client.hset(redis_key, key, serialized)
            return
    except (OSError, ConnectionError, TimeoutError) as e:
        logger.warning("Redis hset failed for %s: %s — using in-process dict", redis_key, e)
    except Exception as e:
        logger.warning("Redis hset unexpected error for %s: %s — using in-process dict", redis_key, e)

    _MEMORY.setdefault(run_id, {})[key] = serialized


async def sm_get(run_id: str, key: str) -> Any | None:
    """Get a single field from the shared memory hash.

    Args:
        run_id: Orchestration / workspace run identifier.
        key: Field name.

    Returns:
        Parsed JSON value, raw string, or None if missing.
    """
    redis_key = _hash_key(run_id)
    raw: str | None = None
    try:
        if hasattr(redis_client, "hget"):
            raw = await redis_client.hget(redis_key, key)
    except (OSError, ConnectionError, TimeoutError) as e:
        logger.warning("Redis hget failed for %s: %s — using in-process dict", redis_key, e)
    except Exception as e:
        logger.warning("Redis hget unexpected error for %s: %s — using in-process dict", redis_key, e)

    if raw is None:
        raw = _MEMORY.get(run_id, {}).get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def sm_get_all(run_id: str) -> dict[str, Any]:
    """Return the entire shared memory hash for ``run_id``.

    Args:
        run_id: Orchestration / workspace run identifier.

    Returns:
        Mapping of field name → parsed value.
    """
    redis_key = _hash_key(run_id)
    data: dict[str, str] = {}
    try:
        if hasattr(redis_client, "hgetall"):
            data = await redis_client.hgetall(redis_key) or {}
    except (OSError, ConnectionError, TimeoutError) as e:
        logger.warning("Redis hgetall failed for %s: %s — using in-process dict", redis_key, e)
    except Exception as e:
        logger.warning("Redis hgetall unexpected error for %s: %s — using in-process dict", redis_key, e)

    if not data:
        data = dict(_MEMORY.get(run_id, {}))

    result: dict[str, Any] = {}
    for k, v in data.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            result[k] = v
    return result


async def sm_clear(run_id: str) -> None:
    """Delete the shared memory hash for ``run_id``."""
    redis_key = _hash_key(run_id)
    try:
        if hasattr(redis_client, "delete"):
            await redis_client.delete(redis_key)
    except (OSError, ConnectionError, TimeoutError) as e:
        logger.warning("Redis delete failed for %s: %s", redis_key, e)
    except Exception as e:
        logger.warning("Redis delete unexpected error for %s: %s", redis_key, e)
    _MEMORY.pop(run_id, None)


async def sm_replace_all(run_id: str, memory: dict[str, Any]) -> None:
    """Replace the entire shared memory hash with ``memory``.

    Args:
        run_id: Orchestration / workspace run identifier.
        memory: Full memory mapping to persist.
    """
    await sm_clear(run_id)
    for key, value in memory.items():
        await sm_set(run_id, key, value)


def reset_local_store_for_tests() -> None:
    """Clear the in-process fallback store (unit tests only)."""
    _MEMORY.clear()
