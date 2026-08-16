"""
Test Runner — Runs workspace test suites (pytest/jest) as verification steps.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger("devpilot.verification.test_runner")


@dataclass
class TestResult:
    success: bool
    output: str
    exit_code: int


class TestRunner:
    """Invokes system tests on change validation requests."""

    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def run_tests(self, test_files: list[str]) -> TestResult:
        """Run a list of test files using pytest."""
        if not test_files:
            return TestResult(success=True, output="No tests to run.", exit_code=0)

        cmd = ["venv/Scripts/pytest"] + test_files
        from backend.app.agent.security.environment_isolation import (
            EnvironmentIsolation,
        )
        env = EnvironmentIsolation.get_isolated_env()
        try:
            logger.info(f"Running verification tests: {cmd}")
            res = subprocess.run(
                cmd,
                cwd=self.workspace_root or None,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            success = (res.returncode == 0)
            return TestResult(success=success, output=res.stdout + "\n" + res.stderr, exit_code=res.returncode)
        except Exception as e:
            msg = f"Test execution failed: {e}"
            logger.error(msg)
            return TestResult(success=False, output=msg, exit_code=1)


# ── Singleton ───────────────────────────────────────────────────────────────

test_runner = TestRunner()
