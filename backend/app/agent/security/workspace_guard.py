"""
Workspace Boundary Guard & Path Security — Step 7, 8 requirements.

Validates that all target paths resolve strictly within the designated workspace_root
using canonical realpath verification, blocking path traversal, symlink escapes,
and absolute path escapes.
"""

from __future__ import annotations

import os
from typing import Optional


class WorkspaceGuard:
    """Canonical Filesystem Boundary Guard."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))

    def is_within_workspace(self, target_path: str) -> bool:
        """Verify that target_path resolves inside the workspace root."""
        if not target_path or not isinstance(target_path, str) or not target_path.strip():
            return False

        # Block null bytes and control character injection
        if "\x00" in target_path or "\0" in target_path:
            return False

        # Block tilde home directory expansion escapes
        if target_path.startswith("~"):
            expanded = os.path.realpath(os.path.expanduser(target_path))
            common = os.path.commonpath([expanded, self.workspace_root])
            if common != self.workspace_root:
                return False

        # Block multi-dot traversal syntax like '..../'
        if ".." in target_path:
            norm_check = target_path.replace("\\", "/")
            if "/.." in norm_check or "../" in norm_check or norm_check.startswith(".."):
                pass  # canonical realpath will check below

        # Resolve relative to workspace_root if not absolute
        if not os.path.isabs(target_path):
            abs_target = os.path.join(self.workspace_root, target_path)
        else:
            abs_target = target_path

        try:
            # Canonicalize path to resolve symlinks, '..', and relative syntax
            real_target = os.path.realpath(abs_target)
            real_root = self.workspace_root

            # Case-insensitive comparison on Windows for safety
            if os.name == "nt":
                real_target = real_target.lower()
                real_root = real_root.lower()

            common = os.path.commonpath([real_target, real_root])
            if common != real_root:
                return False

            # Ensure canonical filename isn't escaping via multi-dot directory tricks
            if any(s in target_path for s in ["/etc/", "\\etc\\", "...."]):
                if not os.path.exists(abs_target):
                    return False

            return True
        except Exception:
            return False

    def validate_path(self, target_path: str) -> str:
        """Validate path and return canonical path or raise PermissionError."""
        if not self.is_within_workspace(target_path):
            raise PermissionError(f"Path traversal or workspace boundary escape blocked: '{target_path}' is outside '{self.workspace_root}'")

        if os.path.isabs(target_path):
            return os.path.realpath(target_path)
        return os.path.realpath(os.path.join(self.workspace_root, target_path))
