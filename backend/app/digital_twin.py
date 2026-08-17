"""Digital Twin Analysis Service — Real AST and SAST-based workspace quality scoring."""
from __future__ import annotations

import ast
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("loopix.digital_twin")

# Clearly mark this as a real implementation, not a stub
_IMPLEMENTED = True


class DigitalTwinAnalyzer:
    """Performs real static analysis of a workspace to compute a quality score.

    Replaces the previous hardcoded stub that always returned
    ``"READY_FOR_PRODUCTION"`` regardless of actual workspace state.
    """

    def analyze_workspace(self, workspace_path: str) -> dict[str, Any]:
        """Run AST syntax validation + Bandit SAST on the workspace.

        Args:
            workspace_path: Absolute path to the workspace root.

        Returns:
            A dict with ``quality_score``, ``files_analyzed``,
            ``syntax_errors``, ``security_issues``, and ``status``.
        """
        root = Path(workspace_path)
        py_files = list(root.rglob("*.py"))

        # Exclude virtual environments and caches
        exclude = {".venv", "venv", "__pycache__", ".git", "node_modules"}
        py_files = [
            f for f in py_files
            if not any(part in exclude for part in f.parts)
        ]

        syntax_errors = 0
        for f in py_files:
            try:
                ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                syntax_errors += 1
            except Exception:
                pass  # Skip unreadable files

        # Run Bandit for security issue count (best-effort — may not be installed)
        security_issues = 0
        try:
            result = subprocess.run(
                ["bandit", "-r", str(root), "-f", "json", "-q", "--exit-zero"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(result.stdout) if result.stdout.strip() else {}
            security_issues = len(data.get("results", []))
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.debug("bandit not available or timed out — skipping SAST")

        total = len(py_files)
        # Scoring: start at 100, deduct per error/issue
        quality_score = max(
            0.0,
            100.0 - (syntax_errors * 20) - (security_issues * 2),
        )
        status = "HEALTHY" if quality_score >= 70 else "NEEDS_ATTENTION"

        return {
            "implemented": True,
            "quality_score": round(quality_score, 1),
            "files_analyzed": total,
            "syntax_errors": syntax_errors,
            "security_issues": security_issues,
            "status": status,
            "workspace_path": str(root),
        }

    def run_simulation(self, concurrent_users: int = 1000) -> dict[str, Any]:
        """Lightweight simulation stub — clearly marked as non-production data.

        The old implementation returned fabricated production-ready metrics.
        This version clearly flags itself as a simulation/placeholder.
        """
        logger.warning(
            "DigitalTwinSimulator.run_simulation() returns SIMULATED data only. "
            "Do not use these metrics for production capacity planning."
        )
        return {
            "implemented": False,
            "simulation_note": (
                "This is a placeholder simulation. "
                "Real load testing requires an external tool such as Locust or k6."
            ),
            "concurrent_users_requested": concurrent_users,
            "metrics": None,
            "verdict": "SIMULATION_ONLY — not production analysis",
        }


# Singleton instance
digital_twin_analyzer = DigitalTwinAnalyzer()

# Backwards-compat alias used by brain_route.py
digital_twin_simulator = digital_twin_analyzer
