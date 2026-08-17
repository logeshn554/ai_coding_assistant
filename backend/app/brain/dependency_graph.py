"""
Dependency Graph — Module-level and package-level dependency model.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("loopix.brain.dependency_graph")


class DependencyGraph:
    """Calculates import cycles and dependency relationships between files."""

    def __init__(self) -> None:
        self._dependencies: dict[str, set[str]] = {}

    def add_import(self, file_path: str, imported_module: str) -> None:
        """Add a dependency edge indicating file_path imports imported_module."""
        if file_path not in self._dependencies:
            self._dependencies[file_path] = set()
        self._dependencies[file_path].add(imported_module)

    def scan_python_imports(self, file_path: str, content: str) -> None:
        """Parse python file content for import statements."""
        import_pat = re.compile(r'^\s*(?:import|from)\s+([\w\.]+)', re.MULTILINE)
        matches = import_pat.findall(content)
        for match in matches:
            self.add_import(file_path, match)

    def get_dependencies(self, file_path: str) -> list[str]:
        return list(self._dependencies.get(file_path, set()))

    def check_for_cycles(self) -> list[list[str]]:
        """Identify dependency loops/cycles in the graph using DFS."""
        visited: dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]):
            visited[node] = 1
            path.append(node)
            for neighbor in self._dependencies.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor, list(path))
            visited[node] = 2

        for node in self._dependencies:
            if visited.get(node, 0) == 0:
                dfs(node, [])

        return cycles


# ── Singleton ───────────────────────────────────────────────────────────────

dependency_graph = DependencyGraph()
