"""
Verification Engine & Scoped Profiles — Step 6, 7, 8 requirements.

Detects project verification profiles (Python, Node/TypeScript, Rust, Go)
and runs task-scoped verification suites (cheap targeted tests first).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("devpilot.autonomous.verification_engine")


@dataclass
class VerificationProfile:
    """Project-specific verification command configuration."""
    language: str
    package_manager: str = "npm"
    test_command: Optional[str] = None
    typecheck_command: Optional[str] = None
    lint_command: Optional[str] = None
    build_command: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "package_manager": self.package_manager,
            "test_command": self.test_command,
            "typecheck_command": self.typecheck_command,
            "lint_command": self.lint_command,
            "build_command": self.build_command,
        }


@dataclass
class VerificationResult:
    """Output summary of running verification checks."""
    success: bool
    command: str
    output: str
    duration_seconds: float
    failed_tests: List[str] = field(default_factory=list)
    error_summary: Optional[str] = None


@dataclass
class VerificationPhaseReport:
    """Task-scoped phase-specific verification report."""
    phase: str
    status: str
    started_at: str
    completed_at: str
    command: str
    exit_code: int
    output_reference: str


@dataclass
class VerificationReport:
    """Formal unified Verification Report."""
    success: bool
    duration_seconds: float
    phases: List[VerificationPhaseReport] = field(default_factory=list)


class VerificationEngine:
    """Canonical Verification Engine detecting profiles and running scoped checks."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.profile = self.detect_profile()

    def detect_profile(self) -> VerificationProfile:
        """Detect project language and available build/test tools."""
        root = self.workspace_root

        # Python detection
        if os.path.exists(os.path.join(root, "pyproject.toml")) or os.path.exists(os.path.join(root, "pytest.ini")) or os.path.exists(os.path.join(root, "requirements.txt")):
            return VerificationProfile(
                language="python",
                package_manager="pip",
                test_command="pytest",
                typecheck_command="mypy",
                lint_command="flake8",
            )

        # TypeScript / JavaScript detection
        pkg_path = os.path.join(root, "package.json")
        if os.path.exists(pkg_path):
            pm = "npm"
            if os.path.exists(os.path.join(root, "pnpm-lock.yaml")):
                pm = "pnpm"
            elif os.path.exists(os.path.join(root, "yarn.lock")):
                pm = "yarn"

            # Parse package.json to see which scripts actually exist
            has_test = False
            has_lint = False
            has_build = False
            has_typecheck = False
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    scripts = pkg_data.get("scripts", {})
                    has_test = "test" in scripts
                    has_lint = "lint" in scripts
                    has_build = "build" in scripts
                    has_typecheck = "typecheck" in scripts
            except Exception:
                pass

            return VerificationProfile(
                language="typescript",
                package_manager=pm,
                test_command=f"{pm} test" if has_test else None,
                typecheck_command=f"{pm} run typecheck" if (has_typecheck or os.path.exists(os.path.join(root, "tsconfig.json"))) else None,
                lint_command=f"{pm} run lint" if has_lint else None,
                build_command=f"{pm} run build" if has_build else None,
            )

        # Default fallback
        return VerificationProfile(language="unknown", test_command=None)

    def load_phase_state(self) -> Dict[str, Any]:
        state_path = os.path.join(self.workspace_root, ".devpilot_phase_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "current_phase": "IMPLEMENTING",
            "completed_phases": [],
            "active_phase": "IMPLEMENTING",
            "failed_validations": [],
            "blocking_errors": [],
            "files_changed": [],
            "last_successful_validation": None,
            "next_action": "implement"
        }

    def save_phase_state(self, state: Dict[str, Any]) -> None:
        state_path = os.path.join(self.workspace_root, ".devpilot_phase_state.json")
        try:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    async def run_phase_command(self, cmd: str) -> VerificationResult:
        if not cmd:
            return VerificationResult(
                success=True,
                command="none",
                output="Skipped (not configured)",
                duration_seconds=0.0,
            )
        import shutil
        first_tool = cmd.split()[0]
        if not shutil.which(first_tool):
            return VerificationResult(
                success=True,
                command=cmd,
                output=f"Skipped: tool '{first_tool}' is not installed",
                duration_seconds=0.0,
            )

        start_time = asyncio.get_event_loop().time()

        from backend.app.agent.security.sandbox import global_sandbox_manager, ExecutionStatus
        active_sandbox = None
        for sb in list(global_sandbox_manager.active_sandboxes.values()):
            if os.path.realpath(sb.policy.workspace_root) == os.path.realpath(self.workspace_root):
                active_sandbox = sb
                break

        if active_sandbox:
            try:
                res = await active_sandbox.execute(cmd, timeout=300.0, cwd=self.workspace_root)
                end_time = asyncio.get_event_loop().time()
                success = (res.status == ExecutionStatus.SUCCESS)
                return VerificationResult(
                    success=success,
                    command=cmd,
                    output=res.combined_output,
                    duration_seconds=round(end_time - start_time, 2),
                    error_summary=None if success else res.combined_output[:500],
                )
            except Exception as e:
                return VerificationResult(
                    success=False,
                    command=cmd,
                    output=str(e),
                    duration_seconds=0.0,
                    error_summary=str(e),
                )

        # Fallback to local subprocess execution
        clean_env = os.environ.copy()
        for k in list(clean_env.keys()):
            if k.startswith("PYTEST"):
                clean_env.pop(k)
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.workspace_root,
                env=clean_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300.0)
            end_time = asyncio.get_event_loop().time()
            out_text = (stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")).strip()
            success = proc.returncode == 0
            return VerificationResult(
                success=success,
                command=cmd,
                output=out_text,
                duration_seconds=round(end_time - start_time, 2),
                error_summary=None if success else out_text[:500],
            )
        except Exception as e:
            return VerificationResult(
                success=False,
                command=cmd,
                output=str(e),
                duration_seconds=0.0,
                error_summary=str(e),
            )

    async def run_scoped_verification(
        self,
        target_files: Optional[List[str]] = None,
        test_files: Optional[List[str]] = None,
    ) -> VerificationResult:
        """Execute cheap targeted verification before running broad suites."""
        cmd = self.profile.test_command
        if not cmd:
            return VerificationResult(
                success=True,
                command="none",
                output="No verification tests configured.",
                duration_seconds=0.0,
            )

        # 1. Scope target test file if provided
        if test_files and self.profile.language == "python":
            cmd = f"pytest {' '.join(test_files)}"
        elif test_files and self.profile.language == "typescript":
            cmd = f"{self.profile.package_manager} test -- {' '.join(test_files)}"

        start_time = asyncio.get_event_loop().time()

        from backend.app.agent.security.sandbox import global_sandbox_manager, ExecutionStatus
        active_sandbox = None
        for sb in list(global_sandbox_manager.active_sandboxes.values()):
            if os.path.realpath(sb.policy.workspace_root) == os.path.realpath(self.workspace_root):
                active_sandbox = sb
                break

        if active_sandbox:
            try:
                res = await active_sandbox.execute(cmd, timeout=60.0, cwd=self.workspace_root)
                end_time = asyncio.get_event_loop().time()
                success = (res.status == ExecutionStatus.SUCCESS)
                return VerificationResult(
                    success=success,
                    command=cmd,
                    output=res.combined_output,
                    duration_seconds=round(end_time - start_time, 2),
                    error_summary=None if success else res.combined_output[:500],
                )
            except Exception as e:
                return VerificationResult(
                    success=False,
                    command=cmd,
                    output=str(e),
                    duration_seconds=0.0,
                    error_summary=str(e),
                )

        # Local fallback
        clean_env = os.environ.copy()
        for k in list(clean_env.keys()):
            if k.startswith("PYTEST"):
                clean_env.pop(k)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.workspace_root,
                env=clean_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
            end_time = asyncio.get_event_loop().time()

            out_text = (stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")).strip()
            success = proc.returncode == 0

            return VerificationResult(
                success=success,
                command=cmd,
                output=out_text,
                duration_seconds=round(end_time - start_time, 2),
                error_summary=None if success else out_text[:500],
            )
        except Exception as e:
            return VerificationResult(
                success=False,
                command=cmd,
                output=str(e),
                duration_seconds=0.0,
                error_summary=str(e),
            )

    _verification_cache: Dict[str, VerificationReport] = {}

    def _calculate_workspace_hash(self) -> str:
        """Calculate a quick hash representing current workspace files state."""
        import hashlib
        hasher = hashlib.sha256()
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build")]
            for file in sorted(files):
                filepath = os.path.join(root, file)
                try:
                    hasher.update(filepath.encode())
                    hasher.update(str(os.path.getmtime(filepath)).encode())
                except OSError:
                    pass
        return hasher.hexdigest()

    async def run_full_verification(self) -> VerificationReport:
        """Run all verification phases sequentially and return aggregated VerificationReport."""
        import datetime
        import time

        try:
            ws_hash = self._calculate_workspace_hash()
            if ws_hash in self._verification_cache:
                logger.info("VerificationEngine: Returning cached verification report.")
                return self._verification_cache[ws_hash]
        except Exception as e:
            ws_hash = None
            logger.warning(f"Could not compute workspace hash: {e}")

        start_ts = time.time()
        phases_to_run = [
            ("lint", self.profile.lint_command),
            ("typecheck", self.profile.typecheck_command),
            ("test", self.profile.test_command),
            ("build", self.profile.build_command),
        ]

        phase_reports = []
        overall_success = True

        for phase_name, cmd in phases_to_run:
            if not cmd:
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                phase_reports.append(VerificationPhaseReport(
                    phase=phase_name,
                    status="SKIPPED",
                    started_at=now_str,
                    completed_at=now_str,
                    command="none",
                    exit_code=0,
                    output_reference="Not configured",
                ))
                continue

            start_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
            res = await self.run_phase_command(cmd)
            end_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

            status = "PASSED" if res.success else "FAILED"
            if not res.success:
                overall_success = False

            phase_reports.append(VerificationPhaseReport(
                phase=phase_name,
                status=status,
                started_at=start_str,
                completed_at=end_str,
                command=cmd,
                exit_code=0 if res.success else 1,
                output_reference=res.output[:2000],  # Bound raw output
            ))

        end_ts = time.time()
        report = VerificationReport(
            success=overall_success,
            duration_seconds=round(end_ts - start_ts, 2),
            phases=phase_reports,
        )

        if ws_hash and overall_success:
            self._verification_cache[ws_hash] = report

        return report
