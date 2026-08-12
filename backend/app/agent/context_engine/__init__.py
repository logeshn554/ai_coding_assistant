"""
Canonical Repository Intelligence & Context Engine package.
"""

from .context_engine import ContextEngine
from .dependency_graph import DependencyGraph
from .hybrid_ranker import HybridRanker
from .security_filter import SecurityFilter
from .smart_search import SearchResult, SmartSearchEngine
from .symbol_index import SymbolIndex
from .types import (
    AgentContext,
    ContextBudget,
    ContextItem,
    ContextProvenance,
    DiagnosticItem,
    EdgeType,
    EditorContext,
    GitContext,
    GraphEdge,
    GraphNode,
    NodeType,
    Position,
    SelectionRange,
    SymbolInfo,
    SymbolKind,
    WorkspaceContext,
)

__all__ = [
    "ContextEngine",
    "SymbolIndex",
    "DependencyGraph",
    "SmartSearchEngine",
    "SearchResult",
    "HybridRanker",
    "SecurityFilter",
    "AgentContext",
    "ContextItem",
    "ContextProvenance",
    "ContextBudget",
    "EditorContext",
    "GitContext",
    "WorkspaceContext",
    "DiagnosticItem",
    "SymbolInfo",
    "SymbolKind",
    "GraphNode",
    "GraphEdge",
    "NodeType",
    "EdgeType",
    "Position",
    "SelectionRange",
]
