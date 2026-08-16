"""
Gateway Rate Limiter — Per-endpoint, tenant-aware rate limiting with sliding window.

Supports:
  - Sliding window counters per (tenant, endpoint) pair
  - Configurable limits per tier (free/pro/enterprise)
  - Burst allowance for short spikes
  - Cooldown tracking and Retry-After headers
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger("agentos.gateway.rate_limiter")


# ── Configuration ───────────────────────────────────────────────────────────

@dataclass
class RateLimitRule:
    """Rate limit configuration for a specific endpoint pattern."""
    endpoint_pattern: str       # regex or glob pattern
    requests_per_minute: int    # max requests per sliding window
    burst_size: int = 0         # additional burst allowance above base rate
    cooldown_seconds: float = 0 # forced delay after limit is hit
    per_user: bool = True       # if False, limit is per-tenant


# Tier-based default limits
_TIER_DEFAULTS: dict[str, dict[str, int]] = {
    "free": {
        "chat": 20,
        "completion": 30,
        "tools": 60,
        "files": 120,
        "default": 100,
    },
    "pro": {
        "chat": 60,
        "completion": 100,
        "tools": 200,
        "files": 500,
        "default": 300,
    },
    "enterprise": {
        "chat": 300,
        "completion": 500,
        "tools": 1000,
        "files": 2000,
        "default": 1000,
    },
}


class RateLimitResult(str, Enum):
    ALLOWED = "allowed"
    THROTTLED = "throttled"
    BLOCKED = "blocked"


@dataclass
class RateLimitResponse:
    """Result of a rate limit check."""
    result: RateLimitResult
    remaining: int              # requests remaining in current window
    limit: int                  # total limit for the window
    reset_at: float             # unix timestamp when window resets
    retry_after: float = 0.0    # seconds to wait before retrying


# ── Sliding Window Counter ──────────────────────────────────────────────────

@dataclass
class _WindowEntry:
    """Single entry in the sliding window."""
    timestamp: float
    count: int = 1


class SlidingWindowCounter:
    """Token-bucket-style sliding window rate counter."""

    def __init__(self, window_seconds: float = 60.0):
        self._window = window_seconds
        self._entries: list[_WindowEntry] = []

    def _prune(self, now: float) -> None:
        cutoff = now - self._window
        self._entries = [e for e in self._entries if e.timestamp > cutoff]

    @property
    def count(self) -> int:
        self._prune(time.time())
        return sum(e.count for e in self._entries)

    def record(self) -> int:
        """Record a new request and return the current count."""
        now = time.time()
        self._prune(now)
        self._entries.append(_WindowEntry(timestamp=now))
        return self.count

    def oldest_timestamp(self) -> float:
        if not self._entries:
            return 0.0
        return self._entries[0].timestamp

    def reset_at(self) -> float:
        if not self._entries:
            return time.time()
        return self._entries[0].timestamp + self._window


# ── Rate Limiter Engine ─────────────────────────────────────────────────────

class RateLimiter:
    """Per-endpoint, tenant-aware rate limiter."""

    def __init__(self):
        # Key: (tenant_id, user_id, endpoint_category)
        self._windows: dict[tuple[str, str, str], SlidingWindowCounter] = defaultdict(SlidingWindowCounter)
        self._cooldowns: dict[str, float] = {}  # key -> cooldown_until timestamp
        self._custom_rules: dict[str, RateLimitRule] = {}

    def add_rule(self, rule: RateLimitRule) -> None:
        """Register a custom rate limit rule for an endpoint pattern."""
        self._custom_rules[rule.endpoint_pattern] = rule

    def _classify_endpoint(self, path: str) -> str:
        """Classify an endpoint path into a rate limit category."""
        path_lower = path.lower()
        if "/chat" in path_lower or "/ws" in path_lower:
            return "chat"
        elif "/completion" in path_lower or "/generate" in path_lower:
            return "completion"
        elif "/tool" in path_lower or "/execute" in path_lower:
            return "tools"
        elif "/file" in path_lower or "/workspace" in path_lower:
            return "files"
        return "default"

    def _get_limit(self, tier: str, category: str) -> int:
        """Get the rate limit for a tier and category."""
        tier_limits = _TIER_DEFAULTS.get(tier, _TIER_DEFAULTS["free"])
        return tier_limits.get(category, tier_limits["default"])

    def check(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str,
        tier: str = "free",
        multiplier: float = 1.0,
    ) -> RateLimitResponse:
        """Check if a request is allowed under rate limits.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            endpoint: The endpoint path being accessed
            tier: Tenant tier (free/pro/enterprise)
            multiplier: Custom multiplier for the rate limit

        Returns:
            RateLimitResponse with the decision
        """
        category = self._classify_endpoint(endpoint)
        key = (tenant_id, user_id, category)
        key_str = f"{tenant_id}:{user_id}:{category}"

        # Check cooldown
        cooldown_until = self._cooldowns.get(key_str, 0)
        if cooldown_until > 0 and time.time() < cooldown_until:
            return RateLimitResponse(
                result=RateLimitResult.BLOCKED,
                remaining=0,
                limit=0,
                reset_at=cooldown_until,
                retry_after=cooldown_until - time.time(),
            )

        # Get limit
        base_limit = self._get_limit(tier, category)
        effective_limit = max(1, int(base_limit * multiplier))

        # Check burst allowance
        burst = 0
        for rule in self._custom_rules.values():
            if rule.endpoint_pattern in endpoint:
                burst = rule.burst_size
                if rule.cooldown_seconds > 0:
                    pass  # Will apply cooldown if limit hit
                break

        total_limit = effective_limit + burst

        # Record request in sliding window
        window = self._windows[key]
        current_count = window.record()

        if current_count <= total_limit:
            return RateLimitResponse(
                result=RateLimitResult.ALLOWED,
                remaining=max(0, total_limit - current_count),
                limit=total_limit,
                reset_at=window.reset_at(),
            )

        # Rate limited — apply cooldown if configured
        cooldown = 0.0
        for rule in self._custom_rules.values():
            if rule.endpoint_pattern in endpoint and rule.cooldown_seconds > 0:
                cooldown = rule.cooldown_seconds
                self._cooldowns[key_str] = time.time() + cooldown
                break

        retry_after = max(cooldown, window.reset_at() - time.time())
        logger.warning(
            f"Rate limit exceeded: {key_str} ({current_count}/{total_limit}), "
            f"retry_after={retry_after:.1f}s"
        )

        return RateLimitResponse(
            result=RateLimitResult.THROTTLED,
            remaining=0,
            limit=total_limit,
            reset_at=window.reset_at(),
            retry_after=retry_after,
        )

    def reset(self, tenant_id: str = "", user_id: str = "") -> None:
        """Reset rate limits for a specific tenant/user or all."""
        if not tenant_id and not user_id:
            self._windows.clear()
            self._cooldowns.clear()
            return

        keys_to_remove = [
            k for k in self._windows
            if (not tenant_id or k[0] == tenant_id) and (not user_id or k[1] == user_id)
        ]
        for k in keys_to_remove:
            del self._windows[k]

    def get_stats(self) -> dict[str, Any]:
        """Get current rate limiter statistics."""
        stats: dict[str, Any] = {
            "active_windows": len(self._windows),
            "active_cooldowns": sum(
                1 for t in self._cooldowns.values() if t > time.time()
            ),
        }
        return stats


# ── Singleton ───────────────────────────────────────────────────────────────

rate_limiter = RateLimiter()
