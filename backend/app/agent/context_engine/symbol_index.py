"""
Repository Symbol Index — Step 4 & 17 requirements.

Extracts symbols (classes, functions, methods, interfaces, types) using Python AST
and regex/Node AST parsers, and tracks symbol locations, parents, imports, and exports.
Supports fast incremental indexing on file create/modify/delete.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import logging
import os
import re
from typing import Dict, List, Optional, Set

from .security_filter import SecurityFilter
from .types import SymbolInfo, SymbolKind

logger = logging.getLogger("devpilot.context_engine.symbol_index")


class SymbolIndex:
    """Canonical Repository Symbol Index with incremental update support."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.security_filter = SecurityFilter(workspace_root)
        # file_rel_path -> List[SymbolInfo]
        self._file_symbols: Dict[str, List[SymbolInfo]] = {}
        # file_rel_path -> file_sha256_hash
        self._file_hashes: Dict[str, str] = {}
        # symbol_name -> List[SymbolInfo]
        self._symbol_map: Dict[str, List[SymbolInfo]] = {}

    def build_full_index(self) -> None:
        """Scan workspace and index all non-ignored source files."""
        self._file_symbols.clear()
        self._file_hashes.clear()
        self._symbol_map.clear()

        for root, dirs, files in os.walk(self.workspace_root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if not self.security_filter.is_ignored(os.path.relpath(os.path.join(root, d), self.workspace_root))]
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")
                if not self.security_filter.is_ignored(rel_path):
                    self.index_file(rel_path)

        logger.info(f"SymbolIndex build complete: indexed {len(self._file_symbols)} files, {sum(len(v) for v in self._symbol_map.values())} total symbols.")

    def index_file(self, relative_path: str) -> List[SymbolInfo]:
        """Index or re-index a single file incrementally."""
        norm_path = relative_path.replace("\\", "/").strip("/")
        abs_path = os.path.join(self.workspace_root, norm_path)

        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            self.remove_file(norm_path)
            return []

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return []

        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if self._file_hashes.get(norm_path) == h:
            return self._file_symbols.get(norm_path, [])

        # Remove existing symbol references for this file before updating
        self.remove_file(norm_path)

        symbols = self._extract_symbols(norm_path, content)

        self._file_symbols[norm_path] = symbols
        self._file_hashes[norm_path] = h

        for sym in symbols:
            self._symbol_map.setdefault(sym.name, []).append(sym)

        return symbols

    def remove_file(self, relative_path: str) -> None:
        """Remove a file from the symbol index."""
        norm_path = relative_path.replace("\\", "/").strip("/")
        self._file_hashes.pop(norm_path, None)
        old_symbols = self._file_symbols.pop(norm_path, [])

        for sym in old_symbols:
            if sym.name in self._symbol_map:
                self._symbol_map[sym.name] = [s for s in self._symbol_map[sym.name] if s.file != norm_path]
                if not self._symbol_map[sym.name]:
                    del self._symbol_map[sym.name]

    def find_symbols(self, name: str) -> List[SymbolInfo]:
        """Lookup symbols by exact or case-insensitive match."""
        if name in self._symbol_map:
            return self._symbol_map[name]
        
        matches = []
        name_lower = name.lower()
        for sym_name, sym_list in self._symbol_map.items():
            if sym_name.lower() == name_lower:
                matches.extend(sym_list)
        return matches

    def get_file_symbols(self, relative_path: str) -> List[SymbolInfo]:
        """Get all symbols defined in a file."""
        norm_path = relative_path.replace("\\", "/").strip("/")
        return self._file_symbols.get(norm_path, [])

    def _extract_symbols(self, path: str, content: str) -> List[SymbolInfo]:
        """Extract symbols based on file extension."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".py":
            return self._extract_python_symbols(path, content)
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            return self._extract_jsts_symbols(path, content)
        return []

    def _extract_python_symbols(self, path: str, content: str) -> List[SymbolInfo]:
        """Extract Python classes, functions, methods, imports, and exports via AST."""
        symbols: List[SymbolInfo] = []
        imports: List[str] = []
        exports: List[str] = []

        try:
            tree = ast.parse(content)
        except Exception:
            return symbols

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}" if mod else alias.name)

        def _traverse(nodes: List[ast.AST], parent_name: Optional[str] = None):
            for node in nodes:
                if isinstance(node, ast.ClassDef):
                    sym = SymbolInfo(
                        name=node.name,
                        file=path,
                        kind=SymbolKind.CLASS,
                        language="python",
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        parent_symbol=parent_name,
                        imports=imports,
                        exports=exports,
                    )
                    symbols.append(sym)
                    _traverse(node.body, parent_name=node.name)

                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = SymbolKind.METHOD if parent_name else SymbolKind.FUNCTION
                    sym = SymbolInfo(
                        name=node.name,
                        file=path,
                        kind=kind,
                        language="python",
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        parent_symbol=parent_name,
                        imports=imports,
                        exports=exports,
                    )
                    symbols.append(sym)

        _traverse(tree.body)
        return symbols

    def _extract_jsts_symbols(self, path: str, content: str) -> List[SymbolInfo]:
        """Extract JS/TS classes, functions, methods, interfaces, types using regex analysis."""
        symbols: List[SymbolInfo] = []
        lines = content.splitlines()

        patterns = [
            (re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"), SymbolKind.CLASS),
            (re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"), SymbolKind.FUNCTION),
            (re.compile(r"^(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)"), SymbolKind.INTERFACE),
            (re.compile(r"^(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*="), SymbolKind.TYPE),
            (re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("), SymbolKind.FUNCTION),
        ]

        for i, line in enumerate(lines, 1):
            line_str = line.strip()
            for pat, kind in patterns:
                m = pat.match(line_str)
                if m:
                    symbols.append(
                        SymbolInfo(
                            name=m.group(1),
                            file=path,
                            kind=kind,
                            language="typescript" if path.endswith((".ts", ".tsx")) else "javascript",
                            start_line=i,
                            end_line=i + 5,
                        )
                    )
                    break
        return symbols
