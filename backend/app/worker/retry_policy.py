"""
RetryPolicy: Classifies exceptions as retryable vs non-retryable and calculates backoff delays.
Configurable via config/retry_policy.yaml.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("loopix.retry_policy")

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE = 2.0
DEFAULT_BACKOFF_MAX = 30.0

DEFAULT_RETRYABLE: set[str] = {
    "ConnectionError",
    "TimeoutError",
    "asyncio.TimeoutError",
    "httpx.ConnectError",
    "httpx.ReadTimeout",
    "httpx.ConnectTimeout",
    "httpx.RemoteProtocolError",
    "httpx.HTTPStatusError",
    "redis.exceptions.ConnectionError",
    "redis.exceptions.TimeoutError",
    "RateLimitError",
}

DEFAULT_NON_RETRYABLE: set[str] = {
    "ValueError",
    "KeyError",
    "TypeError",
    "FileNotFoundError",
    "PermissionError",
    "RuntimeError",
    "InvalidStateTransitionError",
    "SyntaxError",
    "AuthenticationError",
    "ModuleNotFoundError",
    "AttributeError",
}


class RetryPolicy:
    """Configurable retry policy for worker job and task retries."""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or self._discover_config_path()
        self.max_attempts: int = DEFAULT_MAX_ATTEMPTS
        self.backoff_base_seconds: float = DEFAULT_BACKOFF_BASE
        self.backoff_max_seconds: float = DEFAULT_BACKOFF_MAX
        self.retryable_errors: set[str] = set(DEFAULT_RETRYABLE)
        self.non_retryable_errors: set[str] = set(DEFAULT_NON_RETRYABLE)

        self._load_config()

    def _discover_config_path(self) -> str | None:
        candidates = [
            Path("config/retry_policy.yaml"),
            Path(__file__).resolve().parent.parent.parent.parent / "config" / "retry_policy.yaml",
            Path(__file__).resolve().parent.parent / "config" / "retry_policy.yaml",
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                return str(p)
        return None

    def _load_config(self) -> None:
        if not self.config_path or not os.path.exists(self.config_path):
            logger.debug(f"No retry_policy.yaml found at {self.config_path}. Using built-in defaults.")
            return

        try:
            import yaml
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if isinstance(data, dict):
                self.max_attempts = int(data.get("max_attempts", self.max_attempts))
                self.backoff_base_seconds = float(data.get("backoff_base_seconds", self.backoff_base_seconds))
                self.backoff_max_seconds = float(data.get("backoff_max_seconds", self.backoff_max_seconds))
                
                retryable = data.get("retryable_error_types") or data.get("retryable_errors")
                if isinstance(retryable, list):
                    self.retryable_errors = set(str(x) for x in retryable)

                non_retryable = data.get("non_retryable_error_types") or data.get("non_retryable_errors")
                if isinstance(non_retryable, list):
                    self.non_retryable_errors = set(str(x) for x in non_retryable)

            logger.info(f"Loaded retry policy from {self.config_path}: max_attempts={self.max_attempts}")
        except Exception as e:
            logger.warning(f"Failed to parse retry policy YAML from {self.config_path}: {e}. Using defaults.")

    def is_retryable(self, exc: Exception | type[Exception] | str, attempt: int = 1) -> bool:
        """Determine if an exception should trigger a retry at the given attempt index.

        Args:
            exc: Exception instance, class, or error name/string.
            attempt: Current attempt index (1-based).
        """
        if attempt >= self.max_attempts:
            return False

        if isinstance(exc, type):
            exc_names = {exc.__name__, f"{exc.__module__}.{exc.__name__}"}
        elif isinstance(exc, BaseException):
            cls = exc.__class__
            exc_names = {cls.__name__, f"{cls.__module__}.{cls.__name__}", str(exc)}
        else:
            exc_names = {str(exc)}

        # Check explicit non-retryable first
        for name in exc_names:
            for non_ret in self.non_retryable_errors:
                if non_ret in name or name == non_ret:
                    return False

        # Check explicit retryable
        for name in exc_names:
            for ret in self.retryable_errors:
                if ret in name or name == ret:
                    return True

        # For known transient network keywords in error message
        err_str = str(exc).lower()
        transient_keywords = [
            "timeout",
            "connection refused",
            "connection reset",
            "rate limit",
            "429",
            "503",
            "temporarily unavailable",
            "service unavailable",
        ]
        if any(kw in err_str for kw in transient_keywords):
            return True

        # Default to False for unknown application exceptions (fail-fast)
        return False

    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for a given attempt."""
        delay = self.backoff_base_seconds * (2 ** max(0, attempt - 1))
        return min(delay, self.backoff_max_seconds)


# Default global instance
_default_policy = RetryPolicy()


def is_retryable(exc: Exception | type[Exception] | str, attempt: int = 1) -> bool:
    """Convenience module-level function for checking retry eligibility."""
    return _default_policy.is_retryable(exc, attempt=attempt)
