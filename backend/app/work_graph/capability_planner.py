"""
Capability Planner — Maps intent features and code changes to the required specialist agent capabilities.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Set
from ..intelligence.intent_compiler import CompiledIntent

logger = logging.getLogger("devpilot.work_graph.capability_planner")


class CapabilityPlanner:
    """Selects which agent types (code, test, review, docs, security) are needed for a task."""

    def __init__(self) -> None:
        self._agent_capabilities: Dict[str, Set[str]] = {
            "code": {"write_code", "refactor_code", "implement_feature"},
            "test": {"write_tests", "run_tests", "verify_fixes"},
            "review": {"review_code", "audit_quality"},
            "security": {"scan_security", "check_vulnerabilities"},
            "docs": {"write_docs", "generate_diagrams"},
        }

    def plan_capabilities(self, intent: CompiledIntent) -> List[str]:
        """Determine agent roles required to satisfy the compiled intent."""
        needed_roles = {"code"}  # code is always required
        goal_lower = intent.goal.lower()

        # Check for test / verification needs
        if any(kw in goal_lower for kw in ["test", "verify", "assert", "check"]):
            needed_roles.add("test")

        # Check for review needs
        if any(kw in goal_lower for kw in ["review", "audit", "analyse", "quality"]):
            needed_roles.add("review")

        # Check for security needs
        if any(kw in goal_lower for kw in ["security", "auth", "encrypt", "secret"]):
            needed_roles.add("security")

        # Check for documentation needs
        if any(kw in goal_lower for kw in ["doc", "readme", "comment", "diagram"]):
            needed_roles.add("docs")

        logger.info(f"Planned execution roles for intent: {list(needed_roles)}")
        return list(needed_roles)


# ── Singleton ───────────────────────────────────────────────────────────────

capability_planner = CapabilityPlanner()
