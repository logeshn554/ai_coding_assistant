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

            return VerificationProfile(
                language="typescript",
                package_manager=pm,
                test_command=f"{pm} test",
                typecheck_command=f"{pm} run typecheck" if os.path.exists(os.path.join(root, "tsconfig.json")) else None,
                lint_command=f"{pm} run lint",
                build_command=f"{pm} run build",
            )

        # Default fallback
        return VerificationProfile(language="python", test_command="pytest")

    async def run_scoped_verification(
        self,
        target_files: Optional[List[str]] = None,
        test_files: Optional[List[str]] = None,
    ) -> VerificationResult:
        """Execute cheap targeted verification before running broad suites."""
        # 1. Scope target test file if provided
        cmd = self.profile.test_command or "pytest"
        if test_files and self.profile.language == "python":
            cmd = f"pytest {' '.join(test_files)}"
        elif test_files and self.profile.language == "typescript":
            cmd = f"{self.profile.package_manager} test -- {' '.join(test_files)}"

        start_time = asyncio.get_event_loop().time()

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.workspace_root,
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
