"""
Dependency Graph & Relationships Engine — Step 5 & 6 requirements.

Builds and traverses an in-memory graph representing code relationships
(imports, calls, defines, tests, API routes, configurations).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Dict, List, Optional, Set, Tuple

from .types import EdgeType, GraphEdge, GraphNode, NodeType


class DependencyGraph:
    """Repository Dependency Graph tracking nodes and directional relationship edges."""

    def __init__(self) -> None:
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        # node_id -> list of outgoing edge indices
        self._outgoing: Dict[str, List[GraphEdge]] = {}
        # node_id -> list of incoming edge indices
        self._incoming: Dict[str, List[GraphEdge]] = {}

    def add_node(self, node_id: str, name: str, node_type: NodeType, path: Optional[str] = None, metadata: Optional[dict] = None) -> GraphNode:
        """Add or retrieve a node in the graph."""
        if node_id in self.nodes:
            return self.nodes[node_id]

        node = GraphNode(id=node_id, name=name, type=node_type, path=path, metadata=metadata or {})
        self.nodes[node_id] = node
        self._outgoing[node_id] = []
        self._incoming[node_id] = []
        return node

    def add_edge(self, source_id: str, target_id: str, edge_type: EdgeType, metadata: Optional[dict] = None) -> GraphEdge:
        """Add a directional edge between two nodes."""
        edge = GraphEdge(source_id=source_id, target_id=target_id, edge_type=edge_type, metadata=metadata or {})
        self.edges.append(edge)

        self._outgoing.setdefault(source_id, []).append(edge)
        self._incoming.setdefault(target_id, []).append(edge)
        return edge

    def find_callers(self, symbol_name: str) -> List[GraphNode]:
        """Find all nodes/symbols that call or reference symbol_name."""
        callers = []
        sym_node_id = f"sym:{symbol_name}"
        if sym_node_id in self._incoming:
            for edge in self._incoming[sym_node_id]:
                if edge.edge_type in (EdgeType.CALLS, EdgeType.REFERENCES, EdgeType.IMPORTS):
                    if edge.source_id in self.nodes:
                        callers.append(self.nodes[edge.source_id])
        return callers

    def find_callees(self, symbol_name: str) -> List[GraphNode]:
        """Find all symbols called by symbol_name."""
        callees = []
        sym_node_id = f"sym:{symbol_name}"
        if sym_node_id in self._outgoing:
            for edge in self._outgoing[sym_node_id]:
                if edge.edge_type in (EdgeType.CALLS, EdgeType.REFERENCES):
                    if edge.target_id in self.nodes:
                        callees.append(self.nodes[edge.target_id])
        return callees

    def find_tests(self, file_or_symbol: str) -> List[str]:
        """Find test files covering a specific file or symbol."""
        test_files: Set[str] = set()
        clean_name = os.path.basename(file_or_symbol).replace("\\", "/").split(".")[0].lower()

        for node_id, node in self.nodes.items():
            if node.type == NodeType.TEST:
                test_path = node.path or node.name
                if clean_name in os.path.basename(test_path).lower():
                    test_files.add(test_path)

        return sorted(list(test_files))

    def find_related_files(self, file_path: str, max_depth: int = 2) -> List[str]:
        """Traverse graph outward to find files directly connected via imports/calls."""
        norm_path = file_path.replace("\\", "/").strip("/")
        file_node_id = f"file:{norm_path}"

        related: Set[str] = set()
        visited: Set[str] = {file_node_id}
        queue: List[Tuple[str, int]] = [(file_node_id, 0)]

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for edge in self._outgoing.get(curr_id, []) + self._incoming.get(curr_id, []):
                next_id = edge.target_id if edge.source_id == curr_id else edge.source_id
                if next_id not in visited:
                    visited.add(next_id)
                    if next_id in self.nodes and self.nodes[next_id].path:
                        p = self.nodes[next_id].path
                        if p and p != norm_path:
                            related.add(p)
                    queue.append((next_id, depth + 1))

        return sorted(list(related))
