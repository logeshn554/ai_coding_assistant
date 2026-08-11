"""
Verification Engine — Evidence-based success validation.

Replaces the fake "Verified system consistency and passing checks." string
with actual test/lint/syntax execution that produces structured results.
"""

from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("agent_runtime.verification")


@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str           # e.g. "pytest", "ruff", "mypy", "syntax"
    status: str         # "passed", "failed", "skipped", "error"
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Aggregated verification result across all checks."""
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    summary: str = ""

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "failed"]

    def to_evidence(self) -> dict[str, Any]:
        """Convert to evidence dict suitable for agent result reporting."""
        return {
            "passed": self.passed,
            "summary": self.summary,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "exit_code": c.exit_code,
                }
                for c in self.checks
            ],
        }


class VerificationEngine:
    """Runs verification checks against a workspace to produce evidence-based results.

    The engine discovers which checks are applicable to the workspace
    (e.g. pytest if there's a pytest.ini or test files, ruff if there's
    a pyproject.toml, etc.) and runs them.
    """

    def __init__(self, workspace_root: str, timeout: float = 120.0) -> None:
        self.workspace_root = workspace_root
        self.timeout = timeout

    async def verify(self, checks: list[str] | None = None) -> VerificationResult:
        """Run verification checks and return structured results.

        Args:
            checks: Specific checks to run. If None, auto-discovers applicable checks.

        Returns:
            VerificationResult with all check outcomes.
        """
        if checks is None:
            checks = self._discover_checks()

        results: list[CheckResult] = []
        for check_name in checks:
            runner = self._get_runner(check_name)
            if runner:
                result = await runner()
                results.append(result)
            else:
                results.append(CheckResult(
                    name=check_name,
                    status="skipped",
                    details={"reason": f"No runner for check '{check_name}'"},
                ))

        all_passed = all(
            r.status in ("passed", "skipped") for r in results
        )
        failed = [r for r in results if r.status == "failed"]

        if all_passed:
            summary = f"All {len(results)} verification checks passed."
        else:
            summary = (
                f"{len(failed)} of {len(results)} checks failed: "
                + ", ".join(r.name for r in failed)
            )

        return VerificationResult(
            passed=all_passed,
            checks=results,
            summary=summary,
        )

    def _discover_checks(self) -> list[str]:
        """Auto-discover which checks are applicable to this workspace."""
        checks = []

        # Always check Python syntax if there are .py files
        has_python = any(
            f.endswith(".py")
            for f in os.listdir(self.workspace_root)
            if os.path.isfile(os.path.join(self.workspace_root, f))
        )

        if has_python:
            checks.append("python_syntax")

        # Check for test infrastructure
        test_indicators = ["pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"]
        has_test_config = any(
            os.path.exists(os.path.join(self.workspace_root, f))
            for f in test_indicators
        )
        # Also check if there are test files
        has_test_files = False
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    has_test_files = True
                    break
            if has_test_files:
                break

        if has_test_config or has_test_files:
            checks.append("pytest")

        return checks

    def _get_runner(self, check_name: str):
        """Get the runner function for a check name."""
        runners = {
            "python_syntax": self._check_python_syntax,
            "pytest": self._check_pytest,
            "ruff": self._check_ruff,
            "mypy": self._check_mypy,
        }
        return runners.get(check_name)

    async def _run_command(self, name: str, cmd: str) -> CheckResult:
        """Run a shell command and capture its output as a CheckResult."""
        import time
        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return CheckResult(
                    name=name,
                    status="error",
                    exit_code=-1,
                    stderr=f"Timed out after {self.timeout}s",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            duration_ms = (time.monotonic() - start) * 1000
            stdout = stdout_bytes.decode("utf-8", errors="replace")[:50_000]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:50_000]
            exit_code = proc.returncode or 0

            return CheckResult(
                name=name,
                status="passed" if exit_code == 0 else "failed",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )

        except FileNotFoundError:
            return CheckResult(
                name=name,
                status="skipped",
                details={"reason": f"Command not found: {cmd.split()[0]}"},
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:
            return CheckResult(
                name=name,
                status="error",
                exit_code=-1,
                stderr=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    async def _check_python_syntax(self) -> CheckResult:
        """Check Python syntax by compiling all .py files."""
        import time
        start = time.monotonic()
        errors = []

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            for f in files:
                if not f.endswith(".py"):
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.workspace_root)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                        source = fh.read()
                    compile(source, rel_path, "exec")
                except SyntaxError as e:
                    errors.append(f"{rel_path}:{e.lineno}: {e.msg}")

        duration_ms = (time.monotonic() - start) * 1000

        if errors:
            return CheckResult(
                name="python_syntax",
                status="failed",
                exit_code=1,
                stdout="\n".join(errors),
                duration_ms=duration_ms,
                details={"error_count": len(errors)},
            )

        return CheckResult(
            name="python_syntax",
            status="passed",
            exit_code=0,
            stdout="All Python files have valid syntax.",
            duration_ms=duration_ms,
        )

    async def _check_pytest(self) -> CheckResult:
        """Run pytest and capture results."""
        return await self._run_command("pytest", "python -m pytest --tb=short -q")

    async def _check_ruff(self) -> CheckResult:
        """Run ruff linter."""
        return await self._run_command("ruff", "ruff check .")

    async def _check_mypy(self) -> CheckResult:
        """Run mypy type checker."""
        return await self._run_command("mypy", "mypy . --ignore-missing-imports")
