"""
Phase 6: Deep Code Intelligence & Semantic Understanding.

Provides AST-aware indexing, SymbolGraph relation tracking (defines, imports, calls, extends,
implements, references, overrides, depends-on), ImpactAnalyzer for change blast radius,
and BackgroundIndexer for non-blocking incremental repository index updates.
"""

from __future__ import annotations

import ast
import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SymbolDefinition:
    name: str
    kind: str  # function | class | method | variable | import | interface | decorator
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)


@dataclass
class SymbolRelation:
    source_symbol: str
    target_symbol: str
    relation_type: str  # defines | imports | calls | extends | implements | references | overrides | depends-on
    file_path: str
    line_no: int = 1


@dataclass
class ImpactReport:
    target_symbol: str
    file_path: str
    affected_callers: List[str] = field(default_factory=list)
    affected_dependents: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    impact_score: float = 0.0


class SymbolGraph:
    """Directed graph representing semantic symbol relationships across files."""

    def __init__(self) -> None:
        self.symbols: Dict[str, SymbolDefinition] = {}
        self.relations: List[SymbolRelation] = []

    def add_symbol(self, symbol: SymbolDefinition) -> None:
        key = f"{symbol.file_path}::{symbol.name}"
        self.symbols[key] = symbol

    def add_relation(self, relation: SymbolRelation) -> None:
        self.relations.append(relation)

    def find_references(self, symbol_name: str) -> List[SymbolRelation]:
        return [r for r in self.relations if r.target_symbol == symbol_name and r.relation_type in ("references", "calls")]

    def find_callers(self, function_name: str) -> List[SymbolRelation]:
        return [r for r in self.relations if r.target_symbol == function_name and r.relation_type == "calls"]

    def find_dependents(self, file_path: str) -> List[str]:
        return list({r.file_path for r in self.relations if r.target_symbol.startswith(file_path)})


class ASTAnalyzer:
    """Parses source files into AST symbols and relationship edges."""

    @classmethod
    def analyze_python_file(cls, file_path: str, content: str) -> Tuple[List[SymbolDefinition], List[SymbolRelation]]:
        symbols: List[SymbolDefinition] = []
        relations: List[SymbolRelation] = []

        try:
            tree = ast.parse(content, filename=file_path)
        except Exception:
            return symbols, relations

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                decs = [ast.unparse(d) for d in node.decorator_list]
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="function",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        docstring=ast.get_docstring(node),
                        decorators=decs,
                    )
                )
                # Analyze calls inside function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = ""
                        if isinstance(child.func, ast.Name):
                            call_name = child.func.id
                        elif isinstance(child.func, ast.Attribute):
                            call_name = child.func.attr
                        if call_name:
                            relations.append(
                                SymbolRelation(
                                    source_symbol=node.name,
                                    target_symbol=call_name,
                                    relation_type="calls",
                                    file_path=file_path,
                                    line_no=child.lineno,
                                )
                            )

            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="class",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        docstring=ast.get_docstring(node),
                    )
                )
                for base in node.bases:
                    base_name = ast.unparse(base)
                    relations.append(
                        SymbolRelation(
                            source_symbol=node.name,
                            target_symbol=base_name,
                            relation_type="extends",
                            file_path=file_path,
                            line_no=node.lineno,
                        )
                    )

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        relations.append(
                            SymbolRelation(
                                source_symbol=file_path,
                                target_symbol=f"{node.module}.{alias.name}",
                                relation_type="imports",
                                file_path=file_path,
                                line_no=node.lineno,
                            )
                        )

        return symbols, relations


class ImpactAnalyzer:
    """Calculates change blast radius before modifying symbols."""

    def __init__(self, graph: SymbolGraph) -> None:
        self.graph = graph

    def calculate_impact(self, symbol_name: str, file_path: str) -> ImpactReport:
        callers = [r.source_symbol for r in self.graph.find_callers(symbol_name)]
        refs = [r.file_path for r in self.graph.find_references(symbol_name)]

        affected_tests = [f for f in refs if "test" in f.lower()]
        dependents = list(set(refs) - set(affected_tests))

        score = min(1.0, (len(callers) * 0.3 + len(dependents) * 0.2 + len(affected_tests) * 0.4))

        return ImpactReport(
            target_symbol=symbol_name,
            file_path=file_path,
            affected_callers=callers,
            affected_dependents=dependents,
            affected_tests=affected_tests,
            impact_score=round(score, 2),
        )


class BackgroundIndexer:
    """Asynchronously indexes workspace files in background without blocking editor."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.graph = SymbolGraph()
        self.indexed_files_count = 0
        self.pending_files_count = 0
        self.last_update_ts = 0.0

    async def index_workspace_async(self) -> None:
        self.pending_files_count = 0
        file_list = []

        for root_dir, _, files in os.walk(self.workspace_root):
            for file in files:
                if file.endswith(".py"):
                    file_list.append(os.path.join(root_dir, file))

        self.pending_files_count = len(file_list)

        for fpath in file_list:
            try:
                rel_path = os.path.relpath(fpath, self.workspace_root)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                syms, rels = ASTAnalyzer.analyze_python_file(rel_path, content)
                for s in syms:
                    self.graph.add_symbol(s)
                for r in rels:
                    self.graph.add_relation(r)

                self.indexed_files_count += 1
                self.pending_files_count -= 1
            except Exception:
                pass

        self.last_update_ts = time.time()
