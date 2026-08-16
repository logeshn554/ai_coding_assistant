"""
Canonical Context Engine — Core interface and repository intelligence manager.

Coordinates L0-L4 layered context assembly, symbol index, dependency graph, smart search,
hybrid ranking, security filtering, and context provenance.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from .dependency_graph import DependencyGraph
from .hybrid_ranker import HybridRanker
from .security_filter import SecurityFilter
from .smart_search import SmartSearchEngine
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
    NodeType,
    WorkspaceContext,
)

logger = logging.getLogger("devpilot.context_engine")


class ContextEngine:
    """Canonical Repository Intelligence & Context Engine used by AgentRuntime."""

    _instances: dict[str, ContextEngine] = {}

    def __init__(
        self,
        workspace_root: str,
        organization_id: str = "default-org",
        project_id: str = "default-project",
        workspace_id: str = "default-workspace",
    ) -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.organization_id = organization_id
        self.project_id = project_id
        self.workspace_id = workspace_id
        self.security_filter = SecurityFilter(self.workspace_root)
        self.symbol_index = SymbolIndex(self.workspace_root)
        self.dependency_graph = DependencyGraph()
        self.search_engine = SmartSearchEngine(self.workspace_root, self.symbol_index)
        self.ranker = HybridRanker()
        self.status = "idle"  # idle | indexing | ready
        self.indexed_files = 0
        self.total_files = 0
        self._background_task: asyncio.Task | None = None

    @classmethod
    def get_instance(
        cls,
        workspace_root: str,
        organization_id: str = "default-org",
        project_id: str = "default-project",
        workspace_id: str = "default-workspace",
    ) -> ContextEngine:
        """Get or initialize singleton ContextEngine for a workspace."""
        root = os.path.abspath(workspace_root)
        key = f"{organization_id}:{project_id}:{workspace_id}:{root}"
        if key not in cls._instances:
            cls._instances[key] = cls(root, organization_id, project_id, workspace_id)
        return cls._instances[key]

    def start_background_indexing(self) -> None:
        """Start non-blocking repository symbol and graph indexing."""
        if self.status == "indexing":
            return
        self.status = "indexing"
        try:
            loop = asyncio.get_running_loop()
            self._background_task = loop.create_task(self._index_worker())
        except RuntimeError:
            # Fallback synchronous index if no loop active
            self._index_sync()

    async def _index_worker(self) -> None:
        """Background async worker building symbol index and dependency graph."""
        try:
            await asyncio.to_thread(self._index_sync)
        except Exception as e:
            logger.error(f"Background indexing error: {e}")
        finally:
            self.status = "ready"

    def _index_sync(self) -> None:
        """Synchronous indexing routines."""
        self.symbol_index.build_full_index()
        self._build_dependency_graph()
        self.indexed_files = len(self.symbol_index._file_symbols)
        self.status = "ready"

    def _build_dependency_graph(self) -> None:
        """Populate dependency graph from symbol index imports and files."""
        for rel_path, symbols in self.symbol_index._file_symbols.items():
            file_node_id = f"file:{rel_path}"
            is_test = "test" in rel_path.lower() or rel_path.endswith(("_test.py", ".test.ts", ".spec.ts"))
            node_type = NodeType.TEST if is_test else NodeType.FILE

            self.dependency_graph.add_node(file_node_id, name=rel_path, node_type=node_type, path=rel_path)

            for sym in symbols:
                sym_node_id = f"sym:{sym.name}"
                self.dependency_graph.add_node(sym_node_id, name=sym.name, node_type=NodeType.SYMBOL, path=rel_path)
                self.dependency_graph.add_edge(file_node_id, sym_node_id, EdgeType.DEFINES)

                for imp in sym.imports:
                    imp_node_id = f"file:{imp}"
                    self.dependency_graph.add_edge(file_node_id, imp_node_id, EdgeType.IMPORTS)

    def on_file_changed(self, relative_path: str) -> None:
        """Incremental re-indexing on file creation or modification (Step 17)."""
        if self.security_filter.is_ignored(relative_path):
            return
        symbols = self.symbol_index.index_file(relative_path)
        file_node_id = f"file:{relative_path}"
        is_test = "test" in relative_path.lower()
        self.dependency_graph.add_node(file_node_id, name=relative_path, node_type=NodeType.TEST if is_test else NodeType.FILE, path=relative_path)
        for sym in symbols:
            sym_node_id = f"sym:{sym.name}"
            self.dependency_graph.add_node(sym_node_id, name=sym.name, node_type=NodeType.SYMBOL, path=relative_path)
            self.dependency_graph.add_edge(file_node_id, sym_node_id, EdgeType.DEFINES)

    def on_file_deleted(self, relative_path: str) -> None:
        """Incremental update on file deletion (Step 17)."""
        self.symbol_index.remove_file(relative_path)

    async def build_context(
        self,
        task_description: str,
        workspace: WorkspaceContext,
        editor: EditorContext | None = None,
        git: GitContext | None = None,
        diagnostics: list[DiagnosticItem] | None = None,
        budget: ContextBudget | None = None,
    ) -> AgentContext:
        """Assemble canonical AgentContext package structured across L0-L4 layers."""
        if self.status == "idle":
            self.start_background_indexing()

        b = budget or ContextBudget()
        diag_list = diagnostics or (editor.diagnostics if editor else [])

        candidates: list[ContextItem] = []

        # L0: Immediate Context (Active file & selected text)
        if editor and editor.active_file:
            rel_act = os.path.relpath(editor.active_file, self.workspace_root).replace("\\", "/") if os.path.isabs(editor.active_file) else editor.active_file
            if not self.security_filter.is_ignored(rel_act):
                abs_act = os.path.join(self.workspace_root, rel_act)
                if os.path.isfile(abs_act):
                    try:
                        with open(abs_act, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        score = self.ranker.score_candidate(rel_act, content, task_description, editor=editor, git=git, dependency_distance=0)
                        candidates.append(
                            ContextItem(
                                file=rel_act,
                                content=content[:4000],
                                provenance=ContextProvenance(source="editor", score=score, reason="L0: active open editor file"),
                            )
                        )
                    except Exception:
                        pass

        # L1/L2: Symbol & Search-based Task Context
        search_results = await self.search_engine.search(task_description, max_results=b.max_search_results)
        for sr in search_results:
            abs_sr = os.path.join(self.workspace_root, sr.file)
            if os.path.isfile(abs_sr):
                try:
                    with open(abs_sr, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    start_line = max(1, sr.line - 15)
                    end_line = min(len(lines), sr.line + 25)
                    snippet = "".join(lines[start_line - 1:end_line])

                    score = self.ranker.score_candidate(
                        sr.file,
                        snippet,
                        task_description,
                        editor=editor,
                        git=git,
                        symbol_matched=sr.match_type == "symbol",
                        semantic_sim=sr.score if sr.match_type == "semantic" else 0.5,
                    )

                    candidates.append(
                        ContextItem(
                            file=sr.file,
                            content=snippet,
                            line_start=start_line,
                            line_end=end_line,
                            symbol=sr.symbol,
                            provenance=ContextProvenance(
                                source=f"smart_search_{sr.match_type}",
                                score=score,
                                reason=f"L2: matched task via {sr.match_type} search",
                            ),
                        )
                    )
                except Exception:
                    pass

        # L3: Related Tests Discovery
        test_files = self.dependency_graph.find_tests(task_description)
        for tf in test_files[:3]:
            abs_tf = os.path.join(self.workspace_root, tf)
            if os.path.isfile(abs_tf):
                try:
                    with open(abs_tf, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    score = self.ranker.score_candidate(tf, content, task_description, editor=editor, git=git, is_test=True)
                    candidates.append(
                        ContextItem(
                            file=tf,
                            content=content[:2000],
                            provenance=ContextProvenance(source="dependency_graph", score=score, reason="L3: related test suite"),
                        )
                    )
                except Exception:
                    pass

        # Perform Hybrid Ranking & Token Budget Truncation
        ranked_items = self.ranker.rank_and_truncate(candidates, b)

        provenance_summary = [
            {
                "file": item.file,
                "score": item.provenance.score if item.provenance else 0.0,
                "source": item.provenance.source if item.provenance else "unknown",
                "reason": item.provenance.reason if item.provenance else "",
            }
            for item in ranked_items
        ]

        symbols_found = []
        for item in ranked_items:
            symbols_found.extend(self.symbol_index.get_file_symbols(item.file))

        total_tokens = sum(len(item.content) for item in ranked_items) // 4

        return AgentContext(
            task_description=task_description,
            workspace_root=self.workspace_root,
            editor=editor,
            git=git,
            diagnostics=diag_list,
            items=ranked_items,
            symbols=symbols_found[:b.max_symbols],
            related_tests=test_files,
            total_tokens_estimate=total_tokens,
            provenance_summary=provenance_summary,
        )

    async def get_debug_info(self, task_description: str) -> dict[str, Any]:
        """Context debugging inspection data for /api/context/debug (Step 22)."""
        search_res = await self.search_engine.search(task_description, max_results=10)
        return {
            "status": self.status,
            "indexed_files": self.indexed_files,
            "total_nodes": len(self.dependency_graph.nodes),
            "total_edges": len(self.dependency_graph.edges),
            "search_results": [
                {
                    "file": r.file,
                    "line": r.line,
                    "match_type": r.match_type,
                    "score": r.score,
                }
                for r in search_res
            ],
        }
