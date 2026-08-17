"""
Smart Code Search & Semantic Retrieval — Step 7 & 8 requirements.

Combines exact text search, regex search, symbol search, and ChromaDB vector search
from backend/app/rag.py, normalizing results into a uniform SearchResult structure.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from .security_filter import SecurityFilter
from .symbol_index import SymbolIndex

logger = logging.getLogger("loopix.context_engine.smart_search")

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "file", "code", "fix",
    "add", "update", "modify", "change", "run", "unit", "test", "issue", "error",
    "bug", "version", "new", "endpoint", "function", "class", "method", "header",
}


@dataclass
class SearchResult:
    """Normalized code search result."""
    file: str
    line: int
    symbol: str | None = None
    snippet: str = ""
    score: float = 1.0
    match_type: str = "text"  # exact | regex | symbol | semantic


class SmartSearchEngine:
    """Unified Code Search Engine."""

    def __init__(self, workspace_root: str, symbol_index: SymbolIndex) -> None:
        self.workspace_root = workspace_root
        self.symbol_index = symbol_index
        self.security_filter = SecurityFilter(workspace_root)

    async def search(
        self,
        query: str,
        match_type: str = "auto",
        path_filter: str | None = None,
        language_filter: str | None = None,
        max_results: int = 20,
    ) -> list[SearchResult]:
        """Perform unified search across exact, regex, symbol, and semantic channels."""
        results: list[SearchResult] = []

        # Tokenize query into distinct search terms for multi-word prompts
        words = re.findall(r"\b[A-Za-z0-9_]{3,}\b", query)
        terms = [w for w in words if w.lower() not in STOPWORDS]
        if not terms:
            terms = [query]

        # 1. Symbol Search for extracted terms and raw query
        for term in terms + [query]:
            sym_matches = self.symbol_index.find_symbols(term)
            for sym in sym_matches:
                if self._matches_filters(sym.file, path_filter, language_filter):
                    results.append(
                        SearchResult(
                            file=sym.file,
                            line=sym.start_line,
                            symbol=sym.name,
                            snippet=f"{sym.kind.value} {sym.name}",
                            score=0.95,
                            match_type="symbol",
                        )
                    )

        # 2. Text / Regex Search across workspace files for extracted terms
        for term in terms:
            text_matches = self._grep_workspace(term, path_filter=path_filter, language_filter=language_filter, limit=max_results)
            results.extend(text_matches)

        # 3. Semantic Search via rag.py if available
        try:
            from backend.app.rag import query as rag_query
            rag_res = await rag_query(self.workspace_root, query, top_k=5)
            if isinstance(rag_res, list):
                for item in rag_res:
                    if isinstance(item, dict):
                        f = item.get("file") or item.get("path") or ""
                        f_rel = os.path.relpath(f, self.workspace_root).replace("\\", "/") if os.path.isabs(f) else f
                        if f_rel and self._matches_filters(f_rel, path_filter, language_filter):
                            results.append(
                                SearchResult(
                                    file=f_rel,
                                    line=item.get("line_start", 1),
                                    snippet=item.get("text", "")[:200],
                                    score=float(item.get("score", 0.7)),
                                    match_type="semantic",
                                )
                            )
        except Exception as e:
            logger.debug(f"ChromaDB semantic search fallback: {e}")

        # Deduplicate results by (file, line)
        seen = set()
        deduped = []
        for r in sorted(results, key=lambda x: x.score, reverse=True):
            key = (r.file, r.line)
            if key not in seen and not self.security_filter.is_ignored(r.file):
                seen.add(key)
                deduped.append(r)
                if len(deduped) >= max_results:
                    break

        return deduped

    def _matches_filters(self, file_path: str, path_filter: str | None, language_filter: str | None) -> bool:
        """Verify path and language filtering rules."""
        if self.security_filter.is_ignored(file_path):
            return False

        if path_filter and path_filter.lower() not in file_path.lower():
            return False

        if language_filter:
            ext = os.path.splitext(file_path)[1].lower()
            lang_exts = {
                "python": (".py",),
                "typescript": (".ts", ".tsx"),
                "javascript": (".js", ".jsx"),
                "css": (".css", ".scss"),
            }
            allowed = lang_exts.get(language_filter.lower(), ())
            if allowed and ext not in allowed:
                return False

        return True

    def _grep_workspace(self, query: str, path_filter: str | None, language_filter: str | None, limit: int) -> list[SearchResult]:
        """Perform exact / regex text search across workspace files."""
        results = []
        try:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        except Exception:
            return []

        count = 0
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if not self.security_filter.is_ignored(os.path.relpath(os.path.join(root, d), self.workspace_root))]
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")

                if not self._matches_filters(rel_path, path_filter, language_filter):
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append(
                                    SearchResult(
                                        file=rel_path,
                                        line=line_num,
                                        snippet=line.strip()[:150],
                                        score=0.8,
                                        match_type="text",
                                    )
                                )
                                count += 1
                                if count >= limit:
                                    return results
                except Exception:
                    pass

        return results
