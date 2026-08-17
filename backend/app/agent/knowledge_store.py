"""Phase 6 — Knowledge Store.

Enhanced semantic workspace index wrapping WorkspaceIndex.
Adds symbol → file mapping, import graph, and incremental updates.

Provides fast lookups for:
  - Which file defines class Foo?
  - Which files import module X?
  - Where are the tests for feature Y?
  - What are all exported symbols?
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("loopix.agent.knowledge_store")

_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist",
              ".next", ".mypy_cache", "build", "out", ".pytest_cache"}
_CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}


@dataclass
class SymbolInfo:
    name: str
    file: str            # relative path
    line: int
    kind: str            # "class", "function", "interface", "type", "variable"
    exported: bool = False


@dataclass
class KnowledgeSnapshot:
    """A point-in-time snapshot of workspace knowledge."""
    # symbol_name → list of SymbolInfo (may be defined in multiple files)
    symbols: dict[str, list[SymbolInfo]] = field(default_factory=dict)
    # file → list of files it imports from
    imports: dict[str, list[str]] = field(default_factory=dict)
    # file → list of files that import it
    imported_by: dict[str, list[str]] = field(default_factory=dict)
    # file → is it a test file?
    test_files: list[str] = field(default_factory=list)
    # all files indexed
    all_files: list[str] = field(default_factory=list)


class KnowledgeStore:
    """Semantic workspace knowledge store.

    Usage:
        store = KnowledgeStore(workspace_root)
        store.build()  # or store.update_file(path) for incremental
        info = store.find_symbol("MyClass")
        imports = store.get_imports("src/auth.py")
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self._snapshot = KnowledgeSnapshot()
        self._built = False

    def build(self) -> None:
        """Full index rebuild — call once per session or after major changes."""
        root = Path(self.workspace_root)
        if not root.is_dir():
            return

        snap = KnowledgeSnapshot()

        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for fname in files:
                fpath = Path(dirpath) / fname
                rel = str(fpath.relative_to(root))
                ext = fpath.suffix.lower()

                if ext not in _CODE_EXTS:
                    continue

                snap.all_files.append(rel)

                if self._is_test_file(fname):
                    snap.test_files.append(rel)

                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    self._extract_symbols(content, rel, ext, snap)
                    self._extract_imports(content, rel, ext, snap)
                except Exception as e:
                    logger.debug(f"KnowledgeStore: skip {rel}: {e}")

        # Build reverse import map
        for src_file, imported_list in snap.imports.items():
            for imp in imported_list:
                if imp not in snap.imported_by:
                    snap.imported_by[imp] = []
                if src_file not in snap.imported_by[imp]:
                    snap.imported_by[imp].append(src_file)

        self._snapshot = snap
        self._built = True
        logger.info(f"KnowledgeStore built: {len(snap.all_files)} files, {len(snap.symbols)} symbols.")

    def update_file(self, rel_path: str) -> None:
        """Incremental update for a single file after it's written/edited."""
        root = Path(self.workspace_root)
        fpath = root / rel_path
        if not fpath.is_file():
            return

        ext = fpath.suffix.lower()
        if ext not in _CODE_EXTS:
            return

        # Remove existing entries for this file
        self._snapshot.symbols = {
            k: [s for s in v if s.file != rel_path]
            for k, v in self._snapshot.symbols.items()
        }
        self._snapshot.symbols = {k: v for k, v in self._snapshot.symbols.items() if v}
        self._snapshot.imports.pop(rel_path, None)

        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            self._extract_symbols(content, rel_path, ext, self._snapshot)
            self._extract_imports(content, rel_path, ext, self._snapshot)
        except Exception as e:
            logger.debug(f"KnowledgeStore: update_file skip {rel_path}: {e}")

    def find_symbol(self, name: str) -> list[SymbolInfo]:
        """Find all definitions of a symbol across the workspace."""
        results = []
        name_lower = name.lower()
        for sym_name, infos in self._snapshot.symbols.items():
            if sym_name.lower() == name_lower:
                results.extend(infos)
        return results

    def search_symbols(self, query: str, max_results: int = 10) -> list[SymbolInfo]:
        """Fuzzy symbol search by prefix or substring."""
        results = []
        query_lower = query.lower()
        for sym_name, infos in self._snapshot.symbols.items():
            if query_lower in sym_name.lower():
                results.extend(infos)
                if len(results) >= max_results:
                    break
        return results[:max_results]

    def get_imports(self, rel_path: str) -> list[str]:
        """Return files imported by a given file."""
        return self._snapshot.imports.get(rel_path, [])

    def get_imported_by(self, rel_path: str) -> list[str]:
        """Return files that import a given file."""
        return self._snapshot.imported_by.get(rel_path, [])

    def get_test_files(self) -> list[str]:
        return self._snapshot.test_files

    def all_files(self) -> list[str]:
        return self._snapshot.all_files

    def to_summary(self) -> str:
        snap = self._snapshot
        return (
            f"Indexed {len(snap.all_files)} source files, "
            f"{len(snap.symbols)} unique symbols, "
            f"{len(snap.test_files)} test files."
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _is_test_file(self, fname: str) -> bool:
        lower = fname.lower()
        return lower.startswith("test_") or lower.endswith("_test.py") or lower.endswith(".test.ts") or lower.endswith(".test.js") or lower.endswith(".spec.ts") or lower.endswith(".spec.js")

    def _extract_symbols(self, content: str, rel: str, ext: str, snap: KnowledgeSnapshot) -> None:
        """Extract class/function/interface definitions."""
        patterns = []
        if ext == ".py":
            patterns = [
                (re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)"), "class", False),
                (re.compile(r"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)"), "function", False),
                (re.compile(r"^([A-Z_][A-Z0-9_]{2,})\s*="), "variable", False),
            ]
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            patterns = [
                (re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"), "class", True),
                (re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"), "function", True),
                (re.compile(r"^(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)"), "interface", True),
                (re.compile(r"^(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*="), "type", True),
                (re.compile(r"^(?:export\s+)?(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("), "function", True),
            ]

        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            for pattern, kind, exported in patterns:
                m = pattern.match(stripped)
                if m:
                    sym_name = m.group(1)
                    info = SymbolInfo(name=sym_name, file=rel, line=lineno, kind=kind, exported=exported)
                    if sym_name not in snap.symbols:
                        snap.symbols[sym_name] = []
                    snap.symbols[sym_name].append(info)
                    break

    def _extract_imports(self, content: str, rel: str, ext: str, snap: KnowledgeSnapshot) -> None:
        """Extract import statements and resolve to relative paths."""
        imports = []
        if ext == ".py":
            for m in re.finditer(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))", content, re.MULTILINE):
                module = m.group(1) or m.group(2)
                if module:
                    imports.append(module.strip().split(".")[0])
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            for m in re.finditer(r"""(?:import|require)\s*[\({]?\s*['"]([^'"]+)['"]""", content):
                path = m.group(1)
                imports.append(path)

        snap.imports[rel] = list(set(imports))
