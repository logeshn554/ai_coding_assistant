import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# ── Symbol kind constants (LSP-compatible) ──
KIND_FILE = 1
KIND_MODULE = 2
KIND_CLASS = 5
KIND_METHOD = 6
KIND_PROPERTY = 7
KIND_FIELD = 8
KIND_CONSTRUCTOR = 9
KIND_FUNCTION = 12
KIND_VARIABLE = 13
KIND_INTERFACE = 11
KIND_TYPE = 26

# ── Per-language regex patterns: (pattern, kind, group_index_for_name) ──
SYMBOL_PATTERNS: Dict[str, List] = {
    "python": [
        (re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_CLASS, 1),
        (re.compile(r"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_FUNCTION, 1),
        (re.compile(r"^([A-Z_][A-Z0-9_]{2,})\s*="), KIND_VARIABLE, 1),  # CONSTANTS
    ],
    "typescript": [
        (re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_CLASS, 1),
        (re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_FUNCTION, 1),
        (re.compile(r"^(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_INTERFACE, 1),
        (re.compile(r"^(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*="), KIND_TYPE, 1),
        (re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(?:async\s*)?\()"), KIND_FUNCTION, 1),
        (re.compile(r"^\s+(?:async\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\("), KIND_METHOD, 1),
    ],
    "javascript": [
        (re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_CLASS, 1),
        (re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"), KIND_FUNCTION, 1),
        (re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(?:async\s*)?\()"), KIND_FUNCTION, 1),
        (re.compile(r"^\s+(?:async\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\("), KIND_METHOD, 1),
    ],
    "css": [
        (re.compile(r"^([.#]?[A-Za-z][A-Za-z0-9_:>~\s\[\]=\"'-]*)\s*\{"), KIND_CLASS, 1),
    ],
}

LANG_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".css": "css",
    ".scss": "css",
}

KIND_NAMES = {
    KIND_CLASS: "class",
    KIND_FUNCTION: "function",
    KIND_METHOD: "method",
    KIND_INTERFACE: "interface",
    KIND_TYPE: "type",
    KIND_VARIABLE: "variable",
    KIND_PROPERTY: "property",
}


class WorkspaceIndex:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        # Cache maps relative_path -> {"mtime": float, "size": int, "first_lines": str}
        self.cache = {}

    def update(self):
        if not self.workspace_root or not os.path.isdir(self.workspace_root):
            return
            
        root_path = Path(self.workspace_root).resolve()
        
        text_extensions = {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", 
            ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".conf",
            ".sh", ".bat", ".dockerfile", "dockerfile"
        }
        
        exclude_dirs = {".git", "node_modules", "venv", ".devpilot", "__pycache__"}
        
        current_paths = set()
        
        for root, dirs, files in os.walk(str(root_path)):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                filepath = Path(root) / file
                ext = filepath.suffix.lower()
                name = filepath.name.lower()
                if ext in text_extensions or name == "dockerfile" or name == "makefile":
                    try:
                        rel_path = filepath.relative_to(root_path).as_posix()
                        current_paths.add(rel_path)
                        
                        stat = filepath.stat()
                        mtime = stat.st_mtime
                        size = stat.st_size
                        
                        cached = self.cache.get(rel_path)
                        if not cached or cached["mtime"] != mtime or cached["size"] != size:
                            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                                lines = []
                                for _ in range(50):
                                    line = f.readline()
                                    if not line:
                                        break
                                    lines.append(line)
                            
                            self.cache[rel_path] = {
                                "mtime": mtime,
                                "size": size,
                                "first_lines": "".join(lines)
                            }
                    except Exception:
                        pass
                        
        for deleted in list(self.cache.keys()):
            if deleted not in current_paths:
                del self.cache[deleted]

    def get_prompt_context(self, max_tokens: int = 2000) -> str:
        """
        Formats workspace context up to max_tokens.
        """
        self.update()
        if not self.cache:
            return ""
            
        max_chars = max_tokens * 4
        parts = ["\n=== Workspace Context (First 50 lines of project files) ==="]
        current_len = len(parts[0])
        
        for rel_path, data in sorted(self.cache.items()):
            file_header = f"\n\nFile: {rel_path}\n---\n"
            content = data["first_lines"]
            
            if current_len + len(file_header) + len(content) > max_chars:
                remaining = max_chars - current_len - len(file_header)
                if remaining > 50:
                    parts.append(file_header + content[:remaining] + "\n... [TRUNCATED due to token limit] ...")
                else:
                    parts.append("\n\n... [ADDITIONAL FILES TRUNCATED due to token limit] ...")
                break
                
            parts.append(file_header + content)
            current_len += len(file_header) + len(content)
            
        return "".join(parts)

    def get_symbols(self, rel_path: str) -> List[Dict[str, Any]]:
        """
        Extract symbols from a workspace file using regex patterns.
        Returns list of {name, kind, kindName, line, col}.
        """
        if not self.workspace_root:
            return []

        ext = Path(rel_path).suffix.lower()
        lang = LANG_BY_EXT.get(ext)
        if not lang:
            return []

        patterns = SYMBOL_PATTERNS.get(lang, [])
        abs_path = Path(self.workspace_root) / rel_path
        if not abs_path.is_file():
            return []

        symbols = []
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, start=1):
                    stripped = line.rstrip("\n\r")
                    for pattern, kind, group_idx in patterns:
                        m = pattern.match(stripped)
                        if m:
                            name = m.group(group_idx).strip()
                            if name and len(name) > 1:
                                col = stripped.index(name) + 1
                                symbols.append({
                                    "name": name,
                                    "kind": kind,
                                    "kindName": KIND_NAMES.get(kind, "symbol"),
                                    "line": line_no,
                                    "col": col,
                                })
                            break  # only first matching pattern per line
        except Exception:
            pass

        return symbols

    def fuzzy_search_files(self, query: str, max_results: int = 50) -> List[str]:
        """
        Token-overlap fuzzy file search over the cached file list.
        Returns relative paths ranked by match quality.
        """
        if not query or not self.workspace_root:
            return []

        # Also scan flat list including uncached files
        exclude_dirs = {".git", "node_modules", "venv", ".devpilot", "__pycache__", "dist", ".pytest_cache"}
        all_files: List[str] = []
        root_path = Path(self.workspace_root).resolve()
        try:
            for root, dirs, files in os.walk(str(root_path)):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    fp = Path(root) / file
                    rel = fp.relative_to(root_path).as_posix()
                    all_files.append(rel)
                    if len(all_files) >= 5000:
                        break
                if len(all_files) >= 5000:
                    break
        except Exception:
            all_files = list(self.cache.keys())

        query_lower = query.lower()
        # Score: exact substring in filename > path contains all chars (subsequence)
        scored = []
        for rel in all_files:
            filename = Path(rel).name.lower()
            rel_lower = rel.lower()
            score = 0
            if query_lower == filename:
                score = 1000
            elif query_lower in filename:
                score = 500 + (len(query_lower) / max(len(filename), 1)) * 100
            elif query_lower in rel_lower:
                score = 200
            else:
                # subsequence match on filename
                si = 0
                for ch in query_lower:
                    idx = filename.find(ch, si)
                    if idx == -1:
                        break
                    si = idx + 1
                    score += 1
                else:
                    score = max(score, 10)

            if score > 0:
                scored.append((score, rel))

        scored.sort(key=lambda x: -x[0])
        return [rel for _, rel in scored[:max_results]]
