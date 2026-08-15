import os
import secrets
import logging
from typing import Optional
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
try:
    import sys
    if sys.platform != "win32":
        # Restrict configuration directory access to owner-only
        os.chmod(token_file.parent, 0o700)
except Exception:
    pass

if token_file.exists():
    try:
        SESSION_TOKEN = token_file.read_text(encoding="utf-8").strip()
        try:
            if sys.platform != "win32":
                os.chmod(token_file, 0o600)
        except Exception:
            pass
    except Exception:
        SESSION_TOKEN = secrets.token_hex(32)
        try:
            token_file.write_text(SESSION_TOKEN, encoding="utf-8")
            try:
                if sys.platform != "win32":
                    os.chmod(token_file, 0o600)
            except Exception:
                pass
        except Exception:
            pass
else:
    SESSION_TOKEN = secrets.token_hex(32)
    try:
        token_file.write_text(SESSION_TOKEN, encoding="utf-8")
        try:
            if sys.platform != "win32":
                os.chmod(token_file, 0o600)
        except Exception:
            pass
    except Exception:
        pass

# Initialize slowapi rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# Initialize shared Redis client
import asyncio
import redis.asyncio as aioredis


class InMemoryFallbackRedis:
    """Redis client wrapper that falls back to in-process storage on failure."""

    # Seconds to wait before re-attempting a Redis connection after a failure.
    RECONNECT_COOLDOWN = 60

    def __init__(self, redis_url: str):
        self.url = redis_url
        # Create the client once with a fixed pool; don't recreate on every request.
        try:
            self.client = aioredis.from_url(
                self.url,
                decode_responses=True,
                max_connections=10,
                socket_timeout=1.0,
                socket_connect_timeout=1.0
            )
        except Exception as exc:
            logger.warning("Failed to create Redis client at init: %s", exc)
            self.client = None
        self.fallback_db: dict[str, str] = {}
        self._fallback_expiry: dict[str, float] = {}  # key → unix expiry time
        self._fallback_hashes: dict[str, dict[str, str]] = {}
        self.use_fallback = False
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

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
        """Mark Redis as offline and log a WARNING or raise in production."""
        import time as _time
        from .config import settings
        is_prod = (getattr(settings, "ENVIRONMENT", "").lower() == "production" and getattr(settings, "MODE", "").lower() == "server")
        if is_prod:
            logger.critical("FATAL: Redis connection failed during %s in production server mode: %s. Failing closed to prevent split-brain state.", operation, exc)
            raise RuntimeError(f"Redis connection failed during {operation} in production: {exc}")

        if self.use_fallback:
            self._last_failure_time = _time.monotonic()
            return
        self.use_fallback = True
        self._last_failure_time = _time.monotonic()
        self.client = None  # Reset client connection pool
        logger.warning(
            "Redis is offline or not configured during %s (%s). "
            "Using in-memory fallback for session context storage in non-production mode.",
            operation,
            exc,
        )

    async def _ensure_client(self):
        """Lazily (re)create the underlying Redis client if needed."""
        if self.client is None:
            self.client = aioredis.from_url(
                self.url,
                decode_responses=True,
                max_connections=10,
                socket_timeout=1.0,
                socket_connect_timeout=1.0
            )
        return self.client

    async def _probe_redis(self) -> bool:
        """Ping Redis to check if it has come back online."""
        import time as _time
        try:
            self.client = None  # Ensure a fresh connection pool is created
            client = await self._ensure_client()
            await client.ping()
            self.use_fallback = False
            return True
        except Exception as exc:
            logger.debug("Redis probe failed: %s", exc)
            self._last_failure_time = _time.monotonic()  # Reset cooldown
            return False

    async def _maybe_recover(self) -> bool:
        """Attempt recovery from fallback mode when cooldown has elapsed.

        Returns:
            True if Redis is usable (not in fallback), False otherwise.
        """
        if not self.use_fallback:
            return True
        async with self._lock:
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

    async def rpush(self, name: str, value: str) -> int:
        """Push a value to the tail of a list, with in-memory fallback."""
        if not await self._maybe_recover():
            bucket = self._fallback_hashes.setdefault(f"list:{name}", [])
            if not isinstance(bucket, list):
                bucket = []
                self._fallback_hashes[f"list:{name}"] = bucket
            bucket.append(value)
            return len(bucket)
        try:
            client = await self._ensure_client()
            return await client.rpush(name, value)
        except Exception as exc:
            self._enter_fallback("rpush", exc)
            bucket = self._fallback_hashes.setdefault(f"list:{name}", [])
            if not isinstance(bucket, list):
                bucket = []
                self._fallback_hashes[f"list:{name}"] = bucket
            bucket.append(value)
            return len(bucket)

    async def rpoplpush(self, source: str, destination: str) -> Optional[str]:
        """Atomically pop from source and push to destination list, with in-memory fallback."""
        if not await self._maybe_recover():
            src_bucket = self._fallback_hashes.setdefault(f"list:{source}", [])
            if not src_bucket:
                return None
            val = src_bucket.pop()
            dst_bucket = self._fallback_hashes.setdefault(f"list:{destination}", [])
            if not isinstance(dst_bucket, list):
                dst_bucket = []
                self._fallback_hashes[f"list:{destination}"] = dst_bucket
            dst_bucket.insert(0, val)
            return val
        try:
            client = await self._ensure_client()
            return await client.rpoplpush(source, destination)
        except Exception as exc:
            self._enter_fallback("rpoplpush", exc)
            src_bucket = self._fallback_hashes.setdefault(f"list:{source}", [])
            if not src_bucket:
                return None
            val = src_bucket.pop()
            dst_bucket = self._fallback_hashes.setdefault(f"list:{destination}", [])
            if not isinstance(dst_bucket, list):
                dst_bucket = []
                self._fallback_hashes[f"list:{destination}"] = dst_bucket
            dst_bucket.insert(0, val)
            return val

    async def lrem(self, name: str, count: int, value: str) -> int:
        """Remove occurrences of value in list, with in-memory fallback."""
        if not await self._maybe_recover():
            bucket = self._fallback_hashes.get(f"list:{name}", [])
            if not isinstance(bucket, list) or not bucket:
                return 0
            removed = 0
            new_list = []
            for item in bucket:
                if item == value and (count == 0 or removed < abs(count)):
                    removed += 1
                else:
                    new_list.append(item)
            self._fallback_hashes[f"list:{name}"] = new_list
            return removed
        try:
            client = await self._ensure_client()
            return await client.lrem(name, count, value)
        except Exception as exc:
            self._enter_fallback("lrem", exc)
            bucket = self._fallback_hashes.get(f"list:{name}", [])
            if not isinstance(bucket, list) or not bucket:
                return 0
            removed = 0
            new_list = []
            for item in bucket:
                if item == value and (count == 0 or removed < abs(count)):
                    removed += 1
                else:
                    new_list.append(item)
            self._fallback_hashes[f"list:{name}"] = new_list
            return removed


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
from .config import config_manager

# Default to the environment variable, persistent last workspace, or empty string
INITIAL_WORKSPACE_ROOT = os.environ.get("INITIAL_WORKSPACE_ROOT") or config_manager.get_last_workspace() or ""

import contextvars
from collections import deque
session_id_var = contextvars.ContextVar("session_id", default=None)
request_latencies = deque(maxlen=100)

class WorkspaceState:
    def __init__(self, initial_root: str):
        self._default_root = initial_root
        self._session_roots = {}
        self._lsp_diagnostics: dict[str, dict[str, list]] = {}  # sid -> relative_path -> list of diagnostic dicts

    @property
    def root(self) -> str:
        sid = session_id_var.get()
        if sid and sid in self._session_roots:
            return self._session_roots[sid]
        return self._default_root

    @root.setter
    def root(self, val: str) -> None:
        sid = session_id_var.get()
        if sid:
            self._session_roots[sid] = val
            # Bounded size check: keep self._session_roots to max 200 sessions
            if len(self._session_roots) > 200:
                oldest_sid = next(iter(self._session_roots))
                self._session_roots.pop(oldest_sid, None)
            return
        self._default_root = val

    @property
    def lsp_diagnostics(self) -> dict:
        sid = session_id_var.get() or "default"
        if sid not in self._lsp_diagnostics:
            self._lsp_diagnostics[sid] = {}
        return self._lsp_diagnostics[sid]

    @lsp_diagnostics.setter
    def lsp_diagnostics(self, val: dict) -> None:
        sid = session_id_var.get() or "default"
        self._lsp_diagnostics[sid] = val

    def evict_session(self, sid: str) -> None:
        """Evict session ID from memory roots mapping to prevent memory leaks."""
        self._session_roots.pop(sid, None)
        _permission_managers.pop(sid, None)
        self._lsp_diagnostics.pop(sid, None)

workspace_state = WorkspaceState(INITIAL_WORKSPACE_ROOT)

# Initialize Permission Manager
_permission_managers = {}

def get_permission_manager() -> PermissionManager:
    sid = session_id_var.get() or "default"
    if sid not in _permission_managers:
        # Bounded size check: keep _permission_managers to max 200 sessions
        if len(_permission_managers) > 200:
            oldest_sid = next(iter(_permission_managers))
            _permission_managers.pop(oldest_sid, None)
        _permission_managers[sid] = PermissionManager(config_manager, workspace_state.root)
    _permission_managers[sid].workspace_root = workspace_state.root
    return _permission_managers[sid]

# Maximum number of pending one-time WebSocket tickets held in process memory.
# Bounded to prevent memory exhaustion from unauthenticated ticket-flooding attacks.
_MAX_WS_TICKETS = 10_000

_ws_tickets: dict[str, dict] = {}
"""
Process-local one-time ticket store for WebSocket handshake authentication.

WARNING: This is a single-worker-only data structure. In a multi-worker
deployment you MUST replace this with Redis or another shared store, otherwise
workers cannot share ticket state and connections will fail non-deterministically.
"""


def create_ws_ticket(
    user_id: str = "default-user",
    tenant_id: str = "default-org",
    workspace_id: str = ""
) -> str:
    import time
    # Evict expired tickets before creating a new one
    now = time.time()
    expired = [t for t, data in list(_ws_tickets.items()) if isinstance(data, dict) and data.get("exp", 0) < now]
    for t in expired:
        _ws_tickets.pop(t, None)
    # Enforce capacity limit to prevent memory exhaustion
    if len(_ws_tickets) >= _MAX_WS_TICKETS:
        # Evict oldest 10 % when at capacity
        items = sorted(_ws_tickets.items(), key=lambda kv: kv[1].get("exp", 0) if isinstance(kv[1], dict) else 0)
        for k, _ in items[: _MAX_WS_TICKETS // 10 + 1]:
            _ws_tickets.pop(k, None)
    ticket = secrets.token_urlsafe(32)
    _ws_tickets[ticket] = {
        "exp": time.time() + 60.0,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id
    }
    return ticket

def verify_ws_ticket(ticket: str) -> Optional[dict]:
    """Verify and consume a one-time WebSocket connection ticket, returning its identity context."""
    if not ticket:
        return None
    import time
    now = time.time()
    expired = [t for t, data in list(_ws_tickets.items()) if isinstance(data, dict) and data.get("exp", 0) < now]
    for t in expired:
        _ws_tickets.pop(t, None)
    if ticket in _ws_tickets:
        ticket_data = _ws_tickets.pop(ticket)
        return ticket_data if isinstance(ticket_data, dict) else {"user_id": "default-user", "tenant_id": "default-org"}
    return None

async def verify_token(request: Request = None):
    """
    Validate the session token from Authorization or X-Session-Token header only.

    Query-parameter tokens (?token=) are no longer accepted. Tokens in URLs
    leak through access logs, browser history, and reverse proxies.

    Set DEVPILOT_NO_AUTH=true to bypass for local development ONLY.
    This flag is blocked in production.
    """
    if os.environ.get("DEVPILOT_NO_AUTH", "").lower() in ("1", "true", "yes"):
        env_mode = os.environ.get("ENVIRONMENT", os.environ.get("NODE_ENV", "development")).lower()
        if env_mode == "production":
            raise RuntimeError("DEVPILOT_NO_AUTH cannot be enabled in production environment")
        return
    if request is None:
        return

    path = request.url.path
    if path == "/" or path.startswith("/assets/") or path.endswith((".js", ".css", ".png", ".jpg", ".svg", ".ico", ".ttf", ".woff", ".woff2", ".html")) or path in ("/auth/token", "/api/auth/token", "/docs", "/openapi.json", "/api/health") or path.startswith("/health/"):
        return

    # Extract token from Bearer header or X-Session-Token header only.
    # Query-parameter tokens (?token=) are explicitly NOT accepted.
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
    if not token:
        token = request.headers.get("X-Session-Token") or request.headers.get("x-session-token") or ""

    from .config import settings
    if not token and settings.ENVIRONMENT != "production":
        return

    # Constant-time compare to prevent timing attacks
    if not token or not secrets.compare_digest(token.encode(), SESSION_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")

