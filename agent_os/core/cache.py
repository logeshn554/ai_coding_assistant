import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple
from agent_os.core.interfaces import ICache

class CacheService(ICache):
    """In-memory cache with O(1) LRU eviction, TTL expiration, and per-category namespacing."""
    def __init__(self, max_size_per_category: int = 1000) -> None:
        self.max_size_per_category = max_size_per_category
        # Structure: {category: OrderedDict[key, (value, expiration_timestamp)]}
        self._store: Dict[str, OrderedDict[str, Tuple[Any, Optional[float]]]] = {}

    def get(self, category: str, key: str) -> Any:
        if category not in self._store:
            return None
        
        entry = self._store[category].get(key)
        if entry is None:
            return None
        
        value, expiration = entry
        if expiration is not None and time.time() > expiration:
            # Expired, clean it up
            self._store[category].pop(key, None)
            return None
            
        # Move to end to mark as recently used
        self._store[category].move_to_end(key)
        return value

    def set(self, category: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        if category not in self._store:
            self._store[category] = OrderedDict()
            
        expiration = time.time() + ttl if ttl is not None else None
        
        if key in self._store[category]:
            self._store[category][key] = (value, expiration)
            self._store[category].move_to_end(key)
        else:
            if len(self._store[category]) >= self.max_size_per_category:
                # Evict LRU (first item)
                self._store[category].popitem(last=False)
            self._store[category][key] = (value, expiration)

    def delete(self, category: str, key: str) -> None:
        if category in self._store:
            self._store[category].pop(key, None)

    def clear(self) -> None:
        self._store.clear()
