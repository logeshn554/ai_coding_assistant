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
    """Redis client wrapper that falls back to in-process storage on failure."""

    # Seconds to wait before re-attempting a Redis connection after a failure.
    RECONNECT_COOLDOWN = 60

    def __init__(self, redis_url: str):
        self.url = redis_url
        # Create the client once with a fixed pool; don't recreate on every request.
        try:
            self.client = aioredis.from_url(self.url, decode_responses=True, max_connections=10)
        except Exception as exc:
            logger.warning("Failed to create Redis client at init: %s", exc)
            self.client = None
        self.fallback_db: dict[str, str] = {}
        self._fallback_expiry: dict[str, float] = {}  # key → unix expiry time
        self._fallback_hashes: dict[str, dict[str, str]] = {}
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

    def _enter_fallback(self, operation: str, exc: Exception) -> None:
        """Mark Redis as offline and log a WARNING."""
        import time as _time
        self.use_fallback = True
        self._last_failure_time = _time.monotonic()
        logger.warning(
            "Redis is offline or not configured during %s (%s). "
            "Using in-memory fallback for session context storage.",
            operation,
            exc,
        )

    async def _ensure_client(self):
        """Lazily (re)create the underlying Redis client if needed."""
        if self.client is None:
            self.client = aioredis.from_url(self.url, decode_responses=True, max_connections=10)
        return self.client

    async def _probe_redis(self) -> bool:
        """Ping Redis to check if it has come back online."""
        try:
            client = await self._ensure_client()
            await client.ping()
            self.use_fallback = False
            return True
        except Exception as exc:
            logger.debug("Redis probe failed: %s", exc)
            return False

    async def _maybe_recover(self) -> bool:
        """Attempt recovery from fallback mode when cooldown has elapsed.

        Returns:
            True if Redis is usable (not in fallback), False otherwise.
        """
        if not self.use_fallback:
            return True
        if self._should_retry_redis():
            await self._probe_redis()
        return not self.use_fallback

    async def get(self, key: str):
        """Get a string value by key, with in-memory fallback."""
        self._evict_expired()
        if not await self._maybe_recover():
            return self.fallback_db.get(key)
        try:
            client = await self._ensure_client()
            return await client.get(key)
        except Exception as exc:
            self._enter_fallback("get", exc)
            return self.fallback_db.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        """Set a string value by key, with optional TTL and in-memory fallback."""
        self._evict_expired()

        def _store_local():
            import time as _time
            self.fallback_db[key] = value
            if ex is not None:
                self._fallback_expiry[key] = _time.monotonic() + ex
            return True

        if not await self._maybe_recover():
            return _store_local()
        try:
            client = await self._ensure_client()
            return await client.set(key, value, ex=ex)
        except Exception as exc:
            self._enter_fallback("set", exc)
            return _store_local()

    async def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None):
        """Set hash field(s), with in-memory fallback.

        Args:
            name: Hash key name.
            key: Single field name (used with ``value``).
            value: Single field value.
            mapping: Optional multi-field mapping.

        Returns:
            Number of fields added (best-effort under fallback).
        """
        fields: dict[str, str] = {}
        if mapping:
            fields.update({str(k): str(v) for k, v in mapping.items()})
        if key is not None and value is not None:
            fields[str(key)] = str(value)

        if not fields:
            return 0

        def _store_local() -> int:
            bucket = self._fallback_hashes.setdefault(name, {})
            added = 0
            for field, val in fields.items():
                if field not in bucket:
                    added += 1
                bucket[field] = val
            return added

        if not await self._maybe_recover():
            return _store_local()
        try:
            client = await self._ensure_client()
            if mapping and (key is None or value is None):
                return await client.hset(name, mapping=fields)
            if len(fields) == 1 and key is not None:
                return await client.hset(name, key, value)
            return await client.hset(name, mapping=fields)
        except Exception as exc:
            self._enter_fallback("hset", exc)
            return _store_local()

    async def hget(self, name: str, key: str):
        """Get a single hash field, with in-memory fallback."""
        if not await self._maybe_recover():
            return self._fallback_hashes.get(name, {}).get(key)
        try:
            client = await self._ensure_client()
            return await client.hget(name, key)
        except Exception as exc:
            self._enter_fallback("hget", exc)
            return self._fallback_hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict:
        """Get all fields of a hash, with in-memory fallback."""
        if not await self._maybe_recover():
            return dict(self._fallback_hashes.get(name, {}))
        try:
            client = await self._ensure_client()
            result = await client.hgetall(name)
            return dict(result) if result else {}
        except Exception as exc:
            self._enter_fallback("hgetall", exc)
            return dict(self._fallback_hashes.get(name, {}))

    async def delete(self, *names: str) -> int:
        """Delete one or more keys (strings or hashes), with in-memory fallback."""
        if not names:
            return 0

        def _store_local() -> int:
            removed = 0
            for name in names:
                if name in self.fallback_db:
                    del self.fallback_db[name]
                    self._fallback_expiry.pop(name, None)
                    removed += 1
                if name in self._fallback_hashes:
                    del self._fallback_hashes[name]
                    removed += 1
            return removed

        if not await self._maybe_recover():
            return _store_local()
        try:
            client = await self._ensure_client()
            return await client.delete(*names)
        except Exception as exc:
            self._enter_fallback("delete", exc)
            return _store_local()

    async def ping(self) -> bool:
        """Ping Redis and return True if reachable.

        On failure, enters fallback mode and returns False.
        """
        try:
            client = await self._ensure_client()
            await client.ping()
            self.use_fallback = False
            return True
        except Exception as exc:
            self._enter_fallback("ping", exc)
            return False


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = InMemoryFallbackRedis(REDIS_URL)


async def check_redis_at_startup() -> bool:
    """Probe Redis connectivity at application startup.

    Logs a WARNING when Redis is unavailable so operators notice early.
    The app continues with the in-memory fallback either way.

    Returns:
        True if Redis responded to ping, False otherwise.
    """
    try:
        ok = await redis_client.ping()
        if ok:
            logger.info("Redis connectivity check succeeded (%s).", REDIS_URL)
            return True
        logger.warning(
            "Redis unavailable at startup (%s). Using in-memory fallback.",
            REDIS_URL,
        )
        return False
    except Exception as exc:
        logger.warning(
            "Redis startup check failed (%s): %s. Using in-memory fallback.",
            REDIS_URL,
            exc,
        )
        return False


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
    """
    Validate the session token from Authorization header or ?token= query param.
    Set DEVPILOT_NO_AUTH=true to bypass for local development.
    """
    if os.environ.get("DEVPILOT_NO_AUTH", "").lower() in ("1", "true", "yes"):
        return
    if request is None:
        return

    path = request.url.path
    if path in ("/auth/token", "/api/auth/token", "/docs", "/openapi.json", "/redoc"):
        return

    # Extract token from Bearer header or query param
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
    if not token:
        token = request.query_params.get("token", "")

    # Allow local requests (127.0.0.1 / localhost) when no token is provided
    client_host = request.client.host if request.client else None
    is_local = (
        client_host is None
        or client_host in ("127.0.0.1", "localhost", "::1", "testclient")
        or client_host.startswith("127.0.0.")
        or client_host.startswith("::ffff:127.0.0.")
    )
    if is_local and not token:
        return

    # Constant-time compare to prevent timing attacks
    if not token or not secrets.compare_digest(token.encode(), SESSION_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
