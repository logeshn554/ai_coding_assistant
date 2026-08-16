"""
Security Scanner — Runs static security audits (semgrep/bandit) on codebase adjustments.
"""
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("devpilot.verification.security_scanner")


class SecurityScanner:
    """Blocks merges containing credentials leaks or remote code execution risks."""

    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def scan_files(self, files: list[str]) -> bool:
        """Run bandit security checker on files."""
        if not files:
            return True

        cmd = ["bandit", "-r"] + files
        from backend.app.agent.security.environment_isolation import (
            EnvironmentIsolation,
        )
        env = EnvironmentIsolation.get_isolated_env()
        try:
            logger.info(f"Running security scan: {cmd}")
            res = subprocess.run(
                cmd,
                cwd=self.workspace_root or None,
                capture_output=True,
                check=False,
                env=env
            )
            # Bandit returns 0 if no issues found, or 1 if low/medium/high issues
            return (res.returncode == 0)
        except Exception as e:
            logger.error(f"Security scanner execution failed: {e}. Failing closed.")
            return False


# ── Singleton ───────────────────────────────────────────────────────────────

security_scanner = SecurityScanner()
