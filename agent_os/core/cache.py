import time
from typing import Any, Dict, Optional, Tuple
from agent_os.core.interfaces import ICache

class CacheService(ICache):
    """In-memory cache with optional TTL expiration."""
    def __init__(self) -> None:
        # Structure: {category: {key: (value, expiration_timestamp)}}
        self._store: Dict[str, Dict[str, Tuple[Any, Optional[float]]]] = {}

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
            
        return value

    def set(self, category: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        if category not in self._store:
            self._store[category] = {}
            
        expiration = time.time() + ttl if ttl is not None else None
        self._store[category][key] = (value, expiration)

    def delete(self, category: str, key: str) -> None:
        if category in self._store:
            self._store[category].pop(key, None)

    def clear(self) -> None:
        self._store.clear()
