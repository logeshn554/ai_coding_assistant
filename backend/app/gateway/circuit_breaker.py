"""
Gateway Circuit Breaker — Protects downstream LLM provider calls.

Implements the circuit breaker pattern with three states:
  - CLOSED: Normal operation, requests pass through
  - OPEN: Provider is failing, requests are rejected immediately
  - HALF_OPEN: Testing if provider has recovered

Supports:
  - Per-provider circuit breakers
  - Configurable failure thresholds and recovery timeouts
  - Automatic fallback to alternative providers
  - Health probing in half-open state
"""
from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("agentos.gateway.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a single circuit breaker."""
    failure_threshold: int = 5          # failures before opening
    success_threshold: int = 3          # successes in half-open before closing
    timeout_seconds: float = 60.0       # how long to stay open before half-open
    window_seconds: float = 120.0       # sliding window for counting failures
    half_open_max_calls: int = 3        # max concurrent calls in half-open
    error_rate_threshold: float = 0.5   # error rate threshold (0-1)
    min_calls_before_trip: int = 3      # minimum calls before evaluating error rate


@dataclass
class CircuitMetrics:
    """Metrics for a circuit breaker instance."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    state_changes: int = 0
    current_state: CircuitState = CircuitState.CLOSED
    opened_at: float = 0.0


class CircuitBreaker:
    """Circuit breaker for a single downstream provider."""

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_timestamps: deque[float] = deque()
        self._success_timestamps: deque[float] = deque()
        self._opened_at: float = 0.0
        self._half_open_calls: int = 0
        self._half_open_successes: int = 0
        self._metrics = CircuitMetrics()
        self._listeners: list[Callable[[str, CircuitState, CircuitState], None]] = []

    @property
    def state(self) -> CircuitState:
        # Auto-transition from OPEN to HALF_OPEN after timeout
        if self._state == CircuitState.OPEN:
            if time.time() - self._opened_at >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def metrics(self) -> CircuitMetrics:
        self._metrics.current_state = self.state
        return self._metrics

    def add_listener(self, listener: Callable[[str, CircuitState, CircuitState], None]) -> None:
        """Add a state change listener: fn(name, old_state, new_state)."""
        self._listeners.append(listener)

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._metrics.state_changes += 1

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._metrics.opened_at = self._opened_at
            logger.warning(f"Circuit breaker '{self.name}' OPENED (failures exceeded threshold)")
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0
            logger.info(f"Circuit breaker '{self.name}' → HALF_OPEN (probing recovery)")
        elif new_state == CircuitState.CLOSED:
            self._failure_timestamps.clear()
            logger.info(f"Circuit breaker '{self.name}' → CLOSED (recovered)")

        for listener in self._listeners:
            try:
                listener(self.name, old_state, new_state)
            except Exception:
                pass

    def _prune_window(self) -> None:
        cutoff = time.time() - self.config.window_seconds
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()
        while self._success_timestamps and self._success_timestamps[0] < cutoff:
            self._success_timestamps.popleft()

    def can_execute(self) -> bool:
        """Check if a call is allowed through the circuit breaker."""
        current_state = self.state  # triggers auto-transition

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.OPEN:
            self._metrics.rejected_calls += 1
            return False

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            self._metrics.rejected_calls += 1
            return False

        return False

    def record_success(self) -> None:
        """Record a successful call."""
        now = time.time()
        self._success_timestamps.append(now)
        self._metrics.total_calls += 1
        self._metrics.successful_calls += 1
        self._metrics.last_success_time = now

        current_state = self.state

        if current_state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def record_failure(self, error: str = "") -> None:
        """Record a failed call."""
        now = time.time()
        self._failure_timestamps.append(now)
        self._metrics.total_calls += 1
        self._metrics.failed_calls += 1
        self._metrics.last_failure_time = now

        if error:
            logger.debug(f"Circuit breaker '{self.name}' failure: {error[:200]}")

        current_state = self.state

        if current_state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            self._transition_to(CircuitState.OPEN)
            return

        if current_state == CircuitState.CLOSED:
            self._prune_window()
            failure_count = len(self._failure_timestamps)
            total_in_window = failure_count + len(self._success_timestamps)

            # Check absolute threshold
            if failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                return

            # Check error rate threshold
            if total_in_window >= self.config.min_calls_before_trip:
                error_rate = failure_count / total_in_window
                if error_rate >= self.config.error_rate_threshold:
                    self._transition_to(CircuitState.OPEN)

    def reset(self) -> None:
        """Force reset the circuit breaker to closed state."""
        self._transition_to(CircuitState.CLOSED)
        self._failure_timestamps.clear()
        self._success_timestamps.clear()
        self._metrics = CircuitMetrics()


# ── Circuit Breaker Registry ────────────────────────────────────────────────

class CircuitBreakerRegistry:
    """Manages circuit breakers for all downstream providers."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()
        self._fallback_order: dict[str, list[str]] = {}

    def get_or_create(self, provider_name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get an existing circuit breaker or create a new one."""
        if provider_name not in self._breakers:
            self._breakers[provider_name] = CircuitBreaker(
                name=provider_name,
                config=config or self._default_config,
            )
        return self._breakers[provider_name]

    def set_fallback_order(self, provider: str, fallbacks: list[str]) -> None:
        """Set the fallback order for a provider when its circuit is open."""
        self._fallback_order[provider] = fallbacks

    def get_available_provider(self, preferred: str) -> str | None:
        """Get the first available provider (circuit closed or half-open)."""
        breaker = self._breakers.get(preferred)
        if breaker is None or breaker.can_execute():
            return preferred

        # Try fallbacks
        fallbacks = self._fallback_order.get(preferred, [])
        for fallback in fallbacks:
            fb_breaker = self._breakers.get(fallback)
            if fb_breaker is None or fb_breaker.can_execute():
                logger.info(f"Falling back from '{preferred}' to '{fallback}'")
                return fallback

        logger.error(f"All providers unavailable for '{preferred}' and its fallbacks")
        return None

    def get_all_metrics(self) -> dict[str, CircuitMetrics]:
        """Get metrics for all circuit breakers."""
        return {name: cb.metrics for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self._breakers.values():
            cb.reset()


# ── Singleton ───────────────────────────────────────────────────────────────

circuit_breaker_registry = CircuitBreakerRegistry()
