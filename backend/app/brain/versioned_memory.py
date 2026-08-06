"""
Versioned Memory — Git-aware session and workspace state tracker.

Associates memory keys with current git hashes, allowing memory recall that corresponds to specific codebase checkpoints.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("devpilot.brain.versioned_memory")


@dataclass
class MemoryVal:
    value: Any
    git_commit: str
    timestamp: float


class VersionedMemory:
    """Stores key-value pairs linked to Git version history."""

    def __init__(self, workspace_root: str = "") -> None:
        self._workspace_root = workspace_root
        self._store: Dict[str, MemoryVal] = {}

    def _get_current_commit(self) -> str:
        if not self._workspace_root:
            return "dirty-no-workspace"
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._workspace_root,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return "dirty-state"

    def set(self, key: str, value: Any) -> None:
        """Store a value linked to the current git commit."""
        import time
        commit = self._get_current_commit()
        self._store[key] = MemoryVal(value=value, git_commit=commit, timestamp=time.time())
        logger.debug(f"Saved versioned memory key '{key}' at commit {commit[:8]}")

    def get(self, key: str, specific_commit: Optional[str] = None) -> Optional[Any]:
        """Retrieve a value.

        If specific_commit is provided, warns if the value was saved on a different commit.
        """
        entry = self._store.get(key)
        if entry is None:
            return None

        if specific_commit and entry.git_commit != specific_commit:
            logger.warning(
                f"Versioned memory key '{key}' was recorded at commit {entry.git_commit[:8]}, "
                f"but requested for commit {specific_commit[:8]}"
            )
        return entry.value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# ── Singleton ───────────────────────────────────────────────────────────────

versioned_memory = VersionedMemory()
