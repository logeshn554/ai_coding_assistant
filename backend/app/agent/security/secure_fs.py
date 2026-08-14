"""
SecureFileSystem — Unified, secure filesystem abstraction for all agent tools.

Ensures that every file read, write, delete, patch, directory list, and search
strictly adheres to workspace boundaries and secret file protection rules.
"""

from __future__ import annotations

import os
import shutil
import glob as py_glob
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .workspace_guard import WorkspaceGuard
from .secret_redactor import SecretRedactor


class SecureFileSystem:
    """Mandatory secure filesystem interface for tools."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.guard = WorkspaceGuard(self.workspace_root)

    def resolve_safe_path(self, target_path: Union[str, Path]) -> str:
        """Resolve a path canonicalized within the workspace or raise PermissionError."""
        path_str = str(target_path).strip()
        if not path_str:
            raise ValueError("Target path cannot be empty")

        if not self.guard.is_within_workspace(path_str):
            raise PermissionError(
                f"Path traversal or boundary escape blocked: '{path_str}' is outside workspace '{self.workspace_root}'"
            )

        if not os.path.isabs(path_str):
            full_path = os.path.join(self.workspace_root, path_str)
        else:
            full_path = path_str

        real_path = os.path.realpath(full_path)
        return real_path

    def read_text(self, target_path: Union[str, Path], encoding: str = "utf-8") -> str:
        safe_path = self.resolve_safe_path(target_path)
        if SecretRedactor.is_secret_file(safe_path):
            raise PermissionError(f"Access to protected secret file is blocked: '{target_path}'")
        if not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File not found: '{target_path}'")
        with open(safe_path, "r", encoding=encoding, errors="replace") as f:
            return f.read()

    def write_text(self, target_path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
        safe_path = self.resolve_safe_path(target_path)
        if SecretRedactor.is_secret_file(safe_path):
            raise PermissionError(f"Modifying protected secret file is blocked: '{target_path}'")
        parent_dir = os.path.dirname(safe_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        # Atomic write via temp file
        temp_path = f"{safe_path}.tmp_{os.getpid()}"
        try:
            with open(temp_path, "w", encoding=encoding) as f:
                f.write(content)
            os.replace(temp_path, safe_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def delete_file(self, target_path: Union[str, Path]) -> bool:
        safe_path = self.resolve_safe_path(target_path)
        if SecretRedactor.is_secret_file(safe_path):
            raise PermissionError(f"Deleting protected secret file is blocked: '{target_path}'")
        if os.path.isfile(safe_path) or os.path.islink(safe_path):
            os.remove(safe_path)
            return True
        elif os.path.isdir(safe_path):
            shutil.rmtree(safe_path)
            return True
        return False

    def list_dir(self, target_path: Union[str, Path] = "") -> List[str]:
        rel = str(target_path).strip() or "."
        safe_path = self.resolve_safe_path(rel)
        if not os.path.isdir(safe_path):
            raise NotADirectoryError(f"Not a directory: '{target_path}'")
        return os.listdir(safe_path)

    def exists(self, target_path: Union[str, Path]) -> bool:
        try:
            safe_path = self.resolve_safe_path(target_path)
            return os.path.exists(safe_path)
        except Exception:
            return False
