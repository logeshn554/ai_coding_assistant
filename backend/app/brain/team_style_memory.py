"""
Team Style Memory — Tracks developer code styles, syntax conventions, and format preferences.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("loopix.brain.team_style_memory")


class TeamStyleMemory:
    """Stores style guidelines (naming conventions, docstring format, test conventions)."""

    def __init__(self) -> None:
        self._guidelines: dict[str, Any] = {
            "naming_style": "snake_case",
            "docstring_format": "google",
            "class_naming": "PascalCase",
            "test_style": "pytest",
            "max_line_length": 120,
            "indentation": "4_spaces"
        }

    def get_preference(self, key: str) -> Any:
        return self._guidelines.get(key)

    def set_preference(self, key: str, value: Any) -> None:
        self._guidelines[key] = value
        logger.info(f"Updated team style preference: {key} -> {value}")

    def import_from_eslint_ruff(self, config_data: dict[str, Any]) -> None:
        """Parse lint configurations to populate style guidelines."""
        if "line-length" in config_data:
            self.set_preference("max_line_length", config_data["line-length"])
        if "indent" in config_data:
            self.set_preference("indentation", config_data["indent"])


# ── Singleton ───────────────────────────────────────────────────────────────

team_style_memory = TeamStyleMemory()
