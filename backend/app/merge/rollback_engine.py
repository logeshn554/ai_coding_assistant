"""
Rollback Engine — Git-based codebase rollback coordinator.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger("devpilot.merge.rollback_engine")


class RollbackEngine:
    """Restores checkout state using git operations on validation errors."""

    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def create_savepoint(self) -> Optional[str]:
        """Record the current Git commit hash to use as a rollback target."""
        if not self.workspace_root:
            return None
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                commit = res.stdout.strip()
                logger.debug(f"Rollback target set: {commit[:8]}")
                return commit
        except Exception as e:
            logger.error(f"Failed to create Git savepoint: {e}")
        return None

    def rollback_to_savepoint(self, savepoint: str) -> bool:
        """Execute a git checkout or reset to return codebase to savepoint commit."""
        if not self.workspace_root or not savepoint:
            return False
        try:
            # First discard local uncommitted changes
            subprocess.run(
                ["git", "reset", "--hard", savepoint],
                cwd=self.workspace_root,
                capture_output=True,
                check=True
            )
            # Remove untracked files
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=self.workspace_root,
                capture_output=True,
                check=True
            )
            logger.warning(f"Rollback Engine: Codebase reset back to savepoint: {savepoint[:8]}")
            return True
        except Exception as e:
            logger.error(f"Git rollback reset failed: {e}")
            return False


# ── Singleton ───────────────────────────────────────────────────────────────

rollback_engine = RollbackEngine()
