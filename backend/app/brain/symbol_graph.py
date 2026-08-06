"""
Symbol Graph — Tracks classes, functions, variables, and symbol locations parsed from the AST.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set

logger = logging.getLogger("devpilot.brain.symbol_graph")


@dataclass
class SymbolNode:
    name: str
    symbol_type: str                   # class | function | method | variable
    file_path: str
    line_number: int
    dependencies: Set[str] = field(default_factory=set)


class SymbolGraph:
    """AST-derived graph showing relationships between classes, functions, and symbols."""

    def __init__(self) -> None:
        self.nodes: Dict[str, SymbolNode] = {}

    def parse_file(self, file_path: str, content: str) -> None:
        """Parse AST of a python file to extract symbol references."""
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    name = node.name
                    self.nodes[name] = SymbolNode(
                        name=name,
                        symbol_type="class",
                        file_path=file_path,
                        line_number=node.lineno
                    )
                elif isinstance(node, ast.FunctionDef):
                    name = node.name
                    self.nodes[name] = SymbolNode(
                        name=name,
                        symbol_type="function",
                        file_path=file_path,
                        line_number=node.lineno
                    )
        except Exception as e:
            logger.error(f"Failed to parse AST for symbol extraction on {file_path}: {e}")

    def add_dependency(self, source_symbol: str, target_symbol: str) -> None:
        """Add a dependency edge between two symbols."""
        src = self.nodes.get(source_symbol)
        if src:
            src.dependencies.add(target_symbol)

    def get_symbol_dependencies(self, symbol_name: str) -> List[str]:
        node = self.nodes.get(symbol_name)
        if not node:
            return []
        return list(node.dependencies)


# ── Singleton ───────────────────────────────────────────────────────────────

symbol_graph = SymbolGraph()
