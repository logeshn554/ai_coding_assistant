"""
Symbol Resolver — Resolves references to classes, functions, and symbols across multiple workspace files.
"""
from __future__ import annotations

import logging
from typing import Optional
from ..brain.symbol_graph import symbol_graph, SymbolNode

logger = logging.getLogger("devpilot.analysis.symbol_resolver")


class SymbolResolver:
    """Finds definitions, references, and paths of individual code symbols."""

    def resolve_symbol(self, symbol_name: str) -> Optional[SymbolNode]:
        """Lookup a symbol declaration in the global Symbol Graph index."""
        node = symbol_graph.nodes.get(symbol_name)
        if node:
            logger.debug(f"Resolved symbol '{symbol_name}' to {node.file_path}:{node.line_number}")
            return node
        return None

    def find_references(self, symbol_name: str) -> List[str]:
        """Find other symbols that explicitly depend on the target symbol."""
        refs = []
        for name, node in symbol_graph.nodes.items():
            if symbol_name in node.dependencies:
                refs.append(name)
        return refs


# ── Singleton ───────────────────────────────────────────────────────────────

symbol_resolver = SymbolResolver()
