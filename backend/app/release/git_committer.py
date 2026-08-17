"""
Git Committer — Commits verified change sets to the Git repository.
"""
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("loopix.release.git_committer")


class GitCommitter:
    """Invokes Git command line utilities to save task commits."""

    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def commit_changes(self, files: list[str], commit_message: str) -> bool:
        """Stage and commit files."""
        if not files:
            return True
        if not self.workspace_root:
            logger.warning("No workspace root configured. Skipping git commit.")
            return False

        from backend.app.agent.security.environment_isolation import (
            EnvironmentIsolation,
        )
        env = EnvironmentIsolation.get_isolated_env()
        try:
            # 1. Stage changes
            subprocess.run(
                ["git", "add"] + files,
                cwd=self.workspace_root,
                capture_output=True,
                check=True,
                env=env
            )
            # 2. Commit changes
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.workspace_root,
                capture_output=True,
                check=True,
                env=env
            )
            logger.info(f"Successfully committed {len(files)} files: '{commit_message}'")
            return True
        except Exception as e:
            logger.error(f"Failed to execute Git commit: {e}")
            return False


# ── Singleton ───────────────────────────────────────────────────────────────

git_committer = GitCommitter()
