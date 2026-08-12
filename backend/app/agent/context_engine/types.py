"""
Context Engine Data Models — Step 2 & 20 requirements.

Provides strongly typed representations for editor context, diagnostics, symbol info,
dependency graph nodes/edges, context items, provenance metadata, context budgets,
and the canonical AgentContext payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SymbolKind(str, Enum):
    """LSP-compatible symbol categories."""
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    METHOD = "method"
    PROPERTY = "property"
    FIELD = "field"
    CONSTRUCTOR = "constructor"
    FUNCTION = "function"
    VARIABLE = "variable"
    INTERFACE = "interface"
    TYPE = "type"
    UNKNOWN = "unknown"


class NodeType(str, Enum):
    """Dependency graph node types."""
    FILE = "FILE"
    SYMBOL = "SYMBOL"
    MODULE = "MODULE"
    TEST = "TEST"
    API_ROUTE = "API_ROUTE"
    CONFIGURATION = "CONFIGURATION"


class EdgeType(str, Enum):
    """Dependency graph relationship edge types."""
    IMPORTS = "imports"
    CALLS = "calls"
    REFERENCES = "references"
    DEFINES = "defines"
    EXPORTS = "exports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    TESTS = "tests"
    ROUTES_TO = "routes_to"
    DEPENDS_ON = "depends_on"
    READS = "reads"
    WRITES = "writes"


@dataclass
class Position:
    line: int
    column: int


@dataclass
class SelectionRange:
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0


@dataclass
class DiagnosticItem:
    """Compiler/Linter/Test diagnostic error or warning (Step 12)."""
    file: str
    message: str
    severity: str = "error"  # error | warning | info
    line: Optional[int] = None
    source: str = "compiler"  # typescript, pytest, flake8, linter, runtime


@dataclass
class EditorContext:
    """Current IDE editor state sent by frontend (Step 11)."""
    active_file: Optional[str] = None
    cursor: Optional[Position] = None
    selection: Optional[SelectionRange] = None
    selected_text: Optional[str] = None
    open_files: List[str] = field(default_factory=list)
    diagnostics: List[DiagnosticItem] = field(default_factory=list)


@dataclass
class GitContext:
    """Repository Git state (Step 13)."""
    branch: Optional[str] = None
    modified_files: List[str] = field(default_factory=list)
    staged_diff: Optional[str] = None
    unstaged_diff: Optional[str] = None
    recent_commits: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkspaceContext:
    """Workspace metadata."""
    workspace_root: str
    name: Optional[str] = None


@dataclass
class SymbolInfo:
    """Structured code symbol representation (Step 4)."""
    name: str
    file: str
    kind: SymbolKind
    language: str
    start_line: int
    end_line: int
    parent_symbol: Optional[str] = None
    module: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    references_count: int = 0


@dataclass
class GraphNode:
    """Dependency graph node (Step 5)."""
    id: str
    name: str
    type: NodeType
    path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Dependency graph edge (Step 5)."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextProvenance:
    """Provenance tracking why context was selected (Step 15)."""
    source: str  # editor | symbol_index | dependency_graph | semantic_search | text_search | git | diagnostics
    score: float
    reason: str


@dataclass
class ContextItem:
    """Single item of ranked context."""
    file: str
    content: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    symbol: Optional[str] = None
    provenance: Optional[ContextProvenance] = None


@dataclass
class ContextBudget:
    """Budget limits for context selection (Step 14)."""
    max_files: int = 15
    max_symbols: int = 30
    max_chars: int = 32000
    max_tokens: int = 8000
    max_search_results: int = 20
    max_graph_depth: int = 3


@dataclass
class AgentContext:
    """Canonical context package passed to AgentRuntime and LLM (Step 20)."""
    task_description: str
    workspace_root: str
    editor: Optional[EditorContext] = None
    git: Optional[GitContext] = None
    diagnostics: List[DiagnosticItem] = field(default_factory=list)
    items: List[ContextItem] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    related_tests: List[str] = field(default_factory=list)
    total_tokens_estimate: int = 0
    provenance_summary: List[Dict[str, Any]] = field(default_factory=list)

    def to_prompt_string(self) -> str:
        """Render context items into a formatted section for the system prompt."""
        parts = []
        if self.editor and self.editor.active_file:
            parts.append(f"Active Editor File: {self.editor.active_file}")
            if self.editor.selected_text:
                parts.append(f"Selected Code:\n```\n{self.editor.selected_text}\n```")

        if self.diagnostics:
            parts.append("Active Diagnostics / Errors:")
            for d in self.diagnostics[:5]:
                parts.append(f"- [{d.severity.upper()}] {d.file}:{d.line or '?'} — {d.message}")

        if self.items:
            parts.append("\nRelevant Repository Context:")
            for item in self.items:
                reason = item.provenance.reason if item.provenance else "relevant"
                loc = f"{item.file}:{item.line_start}-{item.line_end}" if item.line_start else item.file
                parts.append(f"\n--- File: {loc} (Reason: {reason}) ---")
                parts.append(f"```\n{item.content}\n```")

        return "\n".join(parts)
