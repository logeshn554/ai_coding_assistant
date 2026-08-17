"""
Security & Context Pollution Filter — Step 16 requirement.

Filters out secrets, environment files, build artifacts, node_modules, binaries,
large lockfiles, and paths matched by .gitignore patterns.
"""

from __future__ import annotations

import fnmatch
import os
import re

# Directories to unconditionally ignore
DEFAULT_IGNORED_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".loopix",
    "dist",
    "build",
    ".next",
    "out",
    "coverage",
    ".coverage",
    "chroma",
    "artifacts",
}

# File extensions to unconditionally ignore (binaries, media, archives, lockfiles)
DEFAULT_IGNORED_EXTS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".pdf",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".pyd", ".db", ".sqlite", ".sqlite3", ".wasm",
    ".bin", ".dat", ".lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
}

# Patterns indicating sensitive files or secrets
SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"\.env(?:\..*)?$", re.IGNORECASE),
    re.compile(r".*\.pem$", re.IGNORECASE),
    re.compile(r".*\.key$", re.IGNORECASE),
    re.compile(r".*id_rsa.*$", re.IGNORECASE),
    re.compile(r".*credentials.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
]

# Sensitive contents regex checks
SECRET_CONTENT_PATTERNS: list[re.Pattern] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Key ID
    re.compile(r"-----\s*BEGIN\s+PRIVATE\s+KEY\s*-----"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub Personal Access Token
]


class SecurityFilter:
    """Filters workspace files to prevent security leaks and context pollution."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.gitignore_patterns: list[str] = self._load_gitignore_patterns()

    def _load_gitignore_patterns(self) -> list[str]:
        """Parse .gitignore from workspace root if available."""
        patterns = []
        git_ignore_path = os.path.join(self.workspace_root, ".gitignore")
        if os.path.isfile(git_ignore_path):
            try:
                with open(git_ignore_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except Exception:
                pass
        return patterns

    def is_ignored(self, relative_path: str) -> bool:
        """Check if a relative file path should be ignored."""
        norm_path = relative_path.replace("\\", "/").strip("/")
        parts = norm_path.split("/")
        filename = parts[-1]
        basename = os.path.basename(norm_path)

        # 1. Directory check
        for part in parts[:-1]:
            if part in DEFAULT_IGNORED_DIRS or part.startswith("."):
                if part not in (".github", ".vscode", ".agents"):
                    return True

        if parts[0] in DEFAULT_IGNORED_DIRS:
            return True

        # 2. Extension check
        ext = os.path.splitext(filename)[1].lower()
        if ext in DEFAULT_IGNORED_EXTS or filename in DEFAULT_IGNORED_EXTS:
            return True

        # 3. Secret filename pattern check
        for pattern in SECRET_PATTERNS:
            if pattern.search(filename):
                return True

        # 4. Gitignore pattern match
        for pat in self.gitignore_patterns:
            clean_pat = pat.rstrip("/")
            if fnmatch.fnmatch(norm_path, clean_pat) or fnmatch.fnmatch(filename, clean_pat):
                return True

        return False

    def contains_secret(self, content: str) -> bool:
        """Scan file content for hardcoded secret signatures."""
        for pattern in SECRET_CONTENT_PATTERNS:
            if pattern.search(content):
                return True
        return False
