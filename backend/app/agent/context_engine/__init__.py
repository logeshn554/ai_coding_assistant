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
    "AgentContext",
    "ContextBudget",
    "ContextEngine",
    "ContextItem",
    "ContextProvenance",
    "DependencyGraph",
    "DiagnosticItem",
    "EdgeType",
    "EditorContext",
    "GitContext",
    "GraphEdge",
    "GraphNode",
    "HybridRanker",
    "NodeType",
    "Position",
    "SearchResult",
    "SecurityFilter",
    "SelectionRange",
    "SmartSearchEngine",
    "SymbolIndex",
    "SymbolInfo",
    "SymbolKind",
    "WorkspaceContext",
]
