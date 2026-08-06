"""
Impact Analyzer — Analyzes static workspace structures to determine the blast radius of changes.
"""
from __future__ import annotations

import logging
from typing import List, Set
from ..brain.dependency_graph import dependency_graph
from ..brain.test_graph import test_graph

logger = logging.getLogger("devpilot.analysis.impact_analyzer")


class ImpactAnalyzer:
    """Calculates downstream dependencies and test files affected by source modifications."""

    def analyze_file_change(self, file_path: str) -> Set[str]:
        """Determine all files directly or indirectly affected by a modification to file_path."""
        affected = {file_path}
        
        # Traverse dependency graph (files that import file_path)
        visited = set()
        to_visit = [file_path]

        while to_visit:
            current = to_visit.pop(0)
            if current in visited:
                continue
            visited.add(current)

            # Find files that depend on this one
            for node, deps in dependency_graph._dependencies.items():
                if current in deps:
                    affected.add(node)
                    to_visit.append(node)

        logger.info(f"Impact Analysis: Modification to '{file_path}' affects {len(affected)} total files.")
        return affected

    def get_affected_tests(self, modified_files: Set[str]) -> List[str]:
        """Resolve tests associated with any of the modified files."""
        affected_tests = set()
        for f in modified_files:
            tests = test_graph.get_tests_for_file(f)
            affected_tests.update(tests)
        return list(affected_tests)


# ── Singleton ───────────────────────────────────────────────────────────────

impact_analyzer = ImpactAnalyzer()
