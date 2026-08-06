"""
Architecture Rules — Enforces layer communication invariants and architectural guidelines.
"""
from __future__ import annotations

import logging
from typing import List
from ..brain.architecture_graph import architecture_graph
from ..brain.dependency_graph import dependency_graph

logger = logging.getLogger("devpilot.verification.architecture_rules")


class ArchitectureRules:
    """Blocks illegal dependencies (e.g. core kernel code importing frontend/api layer modules)."""

    def validate_dependency_rules(self, file_path: str) -> List[str]:
        """Validate if all imported modules of file_path conform to layer isolation boundaries.

        Returns list of rule violations.
        """
        violations = []
        imports = dependency_graph.get_dependencies(file_path)

        # Heuristic rules:
        # 1. Kernel should never import router or gateway modules
        if "agent_os/kernel" in file_path:
            for imp in imports:
                if "gateway" in imp or "routes" in imp or "adapters" in imp:
                    violations.append(
                        f"Architecture Violation in '{file_path}': Kernel layer "
                        f"is not permitted to import ingress/gateway modules ('{imp}')"
                    )

        if violations:
            logger.warning(f"Architecture validation failed for {file_path}: {violations}")
        else:
            logger.info(f"Architecture validation passed for {file_path}")

        return violations


# ── Singleton ───────────────────────────────────────────────────────────────

architecture_rules = ArchitectureRules()
