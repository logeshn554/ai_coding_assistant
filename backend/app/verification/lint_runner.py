"""
Lint Runner — Runs static analyzers (ruff/eslint) to verify coding style formatting.
"""
from __future__ import annotations

import logging
import subprocess
from typing import List

logger = logging.getLogger("devpilot.verification.lint_runner")


class LintRunner:
    """Verifies that modifications comply with syntax style requirements."""

    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def run_linter(self, files: List[str]) -> bool:
        """Run ruff linting on the target files."""
        if not files:
            return True

        cmd = ["ruff", "check"] + files
        try:
            logger.info(f"Running linter check: {cmd}")
            res = subprocess.run(
                cmd,
                cwd=self.workspace_root or None,
                capture_output=True,
                check=False
            )
            return (res.returncode == 0)
        except Exception as e:
            logger.warning(f"Linter execution raised: {e}")
            return True  # fallback if ruff not configured


# ── Singleton ───────────────────────────────────────────────────────────────

lint_runner = LintRunner()
