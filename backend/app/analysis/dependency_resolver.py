"""
Dependency Resolver — Resolves transitive dependencies and component boundaries for a workspace change set.
"""
from __future__ import annotations

import logging

from ..brain.dependency_graph import dependency_graph

logger = logging.getLogger("loopix.analysis.dependency_resolver")


class DependencyResolver:
    """Computes the topological sorting of modules for execution/validation pipelines."""

    def resolve_transitive_deps(self, files: list[str]) -> list[str]:
        """Produce a topological ordering of files so dependencies are processed first."""
        order: list[str] = []
        visited: set[str] = set()
        temp_visited: set[str] = set()

        def visit(node: str):
            if node in visited:
                return
            if node in temp_visited:
                logger.warning(f"Circular dependency detected during resolution of node '{node}'")
                return

            temp_visited.add(node)
            for dep in dependency_graph.get_dependencies(node):
                # Verify dependency is inside the resolving set
                if dep in files:
                    visit(dep)

            temp_visited.remove(node)
            visited.add(node)
            order.append(node)

        for f in files:
            if f not in visited:
                visit(f)

        return order


# ── Singleton ───────────────────────────────────────────────────────────────

dependency_resolver = DependencyResolver()
