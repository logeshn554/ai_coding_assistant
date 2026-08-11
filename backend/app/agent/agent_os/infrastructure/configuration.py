"""
Configuration — Hierarchical configuration loader managing env, file, and default settings.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger("agentos.infrastructure.configuration")


class Configuration:
    """Combines environment variables and default policies into a uniform interface."""

    def __init__(self) -> None:
        self._defaults: Dict[str, Any] = {
            "agent_os_mode": "sandbox",
            "max_agent_concurrency": 4,
            "cost_limit_usd": 5.0,
            "default_model": "gemini-2.0-flash",
            "debug_mode": True,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Lookup a key in environment variables first, then defaults, then fallback default."""
        env_key = f"DEVPILOT_{key.upper()}"
        if env_key in os.environ:
            val = os.environ[env_key]
            # Simple conversion helper
            if val.lower() in ("true", "1", "yes"):
                return True
            if val.lower() in ("false", "0", "no"):
                return False
            try:
                if "." in val:
                    return float(val)
                return int(val)
            except ValueError:
                return val

        return self._defaults.get(key, default)

    def set_default(self, key: str, value: Any) -> None:
        self._defaults[key] = value


# ── Singleton ───────────────────────────────────────────────────────────────

configuration = Configuration()
