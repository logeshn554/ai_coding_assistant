import os
import secrets
import logging
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
import slowapi.extension
from fastapi import WebSocket
slowapi.extension.Request = (Request, WebSocket)
from .config import ConfigManager
from .permissions import PermissionManager

# Setup Logging
logger = logging.getLogger("devpilot.state")

from pathlib import Path

# Generate session token and setup auth
token_file = Path.home() / ".devpilot" / "session_token.txt"
token_file.parent.mkdir(parents=True, exist_ok=True)
if token_file.exists():
    try:
        SESSION_TOKEN = token_file.read_text(encoding="utf-8").strip()
    except Exception:
        SESSION_TOKEN = secrets.token_hex(32)
        try:
            token_file.write_text(SESSION_TOKEN, encoding="utf-8")
        except Exception:
            pass
else:
    SESSION_TOKEN = secrets.token_hex(32)
    try:
        token_file.write_text(SESSION_TOKEN, encoding="utf-8")
    except Exception:
        pass

# Initialize slowapi rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# Initialize shared Redis client
import redis.asyncio as aioredis

class InMemoryFallbackRedis:
    # Seconds to wait before re-attempting a Redis connection after a failure.
    RECONNECT_COOLDOWN = 60

    def __init__(self, redis_url: str):
        self.url = redis_url
        self.client = None
        self.fallback_db: dict[str, str] = {}
        self._fallback_expiry: dict[str, float] = {}  # key → unix expiry time
        self.use_fallback = False
        self._last_failure_time: float = 0.0

    def _evict_expired(self):
        """Remove stale TTL entries from the fallback store."""
        import time as _time
        now = _time.monotonic()
        expired = [k for k, exp in self._fallback_expiry.items() if exp <= now]
        for k in expired:
            self.fallback_db.pop(k, None)
            del self._fallback_expiry[k]

    def _should_retry_redis(self) -> bool:
        """Return True if enough time has passed to warrant a reconnect attempt."""
        import time as _time
        return _time.monotonic() - self._last_failure_time >= self.RECONNECT_COOLDOWN

    async def get(self, key: str):
        self._evict_expired()
        if self.use_fallback and not self._should_retry_redis():
            return self.fallback_db.get(key)
        try:
            if self.use_fallback:
                # Probe for reconnection
                self.client = aioredis.from_url(self.url, decode_responses=True)
                self.use_fallback = False
            if self.client is None:
                self.client = aioredis.from_url(self.url, decode_responses=True)
            return await self.client.get(key)
        except Exception:
            import time as _time
            self.use_fallback = True
            self._last_failure_time = _time.monotonic()
            logger.info("Redis is offline or not configured. Using in-memory fallback for session context storage.")
            return self.fallback_db.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._evict_expired()
        if self.use_fallback and not self._should_retry_redis():
            import time as _time
            self.fallback_db[key] = value
            if ex is not None:
                self._fallback_expiry[key] = _time.monotonic() + ex
            return True
        try:
            if self.use_fallback:
                self.client = aioredis.from_url(self.url, decode_responses=True)
                self.use_fallback = False
            if self.client is None:
                self.client = aioredis.from_url(self.url, decode_responses=True)
            return await self.client.set(key, value, ex=ex)
        except Exception:
            import time as _time
            self.use_fallback = True
            self._last_failure_time = _time.monotonic()
            logger.info("Redis is offline or not configured. Using in-memory fallback for session context storage.")
            self.fallback_db[key] = value
            if ex is not None:
                self._fallback_expiry[key] = _time.monotonic() + ex
            return True


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = InMemoryFallbackRedis(REDIS_URL)

# Initialize Config Manager
config_manager = ConfigManager()

# Default to the environment variable, persistent last workspace, or empty string
INITIAL_WORKSPACE_ROOT = os.environ.get("INITIAL_WORKSPACE_ROOT") or config_manager.get_last_workspace() or ""

class WorkspaceState:
    def __init__(self, initial_root: str):
        self.root = initial_root

workspace_state = WorkspaceState(INITIAL_WORKSPACE_ROOT)

# Initialize Permission Manager
permission_manager = PermissionManager(config_manager, workspace_state.root)

async def verify_token(request: Request = None):
    # Authentication bypassed
    return
