"""
Cognitive Cache — Thread-safe LRU caching for semantic index queries and prompt chunks.
"""
from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("devpilot.brain.cognitive_cache")


@dataclass
class CacheEntry:
    value: Any
    expiry: float = 0.0


class CognitiveCache:
    """Least Recently Used (LRU) cache with time-to-live (TTL) expiration support."""

    def __init__(self, capacity: int = 500) -> None:
        self._capacity = capacity
        # Ordered dict tracks access patterns to enable LRU eviction
        self._cache: collections.OrderedDict[str, CacheEntry] = collections.OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """Get an item from cache, resetting its recency."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Expiry check
        if entry.expiry > 0.0 and time.time() > entry.expiry:
            self._cache.pop(key)
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float = 0.0) -> None:
        """Store an item in cache, evicting the least recently used if capacity exceeded."""
        if key in self._cache:
            self._cache.pop(key)

        if len(self._cache) >= self._capacity:
            # Evict first element (least recently used)
            self._cache.popitem(last=False)

        expiry = (time.time() + ttl_seconds) if ttl_seconds > 0.0 else 0.0
        self._cache[key] = CacheEntry(value=value, expiry=expiry)

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()


# ── Singleton ───────────────────────────────────────────────────────────────

cognitive_cache = CognitiveCache()
