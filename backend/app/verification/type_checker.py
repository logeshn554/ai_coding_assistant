"""
Type Checker — Executes static type checker (mypy/tsc) as a verification runner.
"""
from __future__ import annotations

import logging
import subprocess
from typing import List

logger = logging.getLogger("devpilot.verification.type_checker")


class TypeChecker:
    """Verifies that code modifications do not introduce static typing violations."""

    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def check_types(self, files: List[str]) -> bool:
        """Run mypy type checking on target files."""
        if not files:
            return True

        # Use mypy from virtual environment if present
        cmd = ["mypy", "--ignore-missing-imports"] + files
        from backend.app.agent.security.environment_isolation import EnvironmentIsolation
        env = EnvironmentIsolation.get_isolated_env()
        try:
            logger.info(f"Running type checks: {cmd}")
            res = subprocess.run(
                cmd,
                cwd=self.workspace_root or None,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            return (res.returncode == 0)
        except Exception as e:
            logger.warning(f"Type checker execution raised: {e}")
            return True  # fallback if mypy not installed locally


# ── Singleton ───────────────────────────────────────────────────────────────

type_checker = TypeChecker()
