"""
Transactional Workspace Manager — Step 6 requirement.

Tracks workspace state snapshots, computes line-by-line diffs, and maintains
a session-level change set (created, modified, deleted files + diffs).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
import hashlib
import os
from typing import Dict, Optional, Set


@dataclass
class FileSnapshot:
    """Snapshot of a single file's state before or after a modification."""
    path: str
    exists: bool
    content: Optional[str] = None
    file_hash: Optional[str] = None


@dataclass
class ChangeSet:
    """Session-level tracking of workspace file modifications."""
    created_files: Set[str] = field(default_factory=set)
    modified_files: Set[str] = field(default_factory=set)
    deleted_files: Set[str] = field(default_factory=set)
    diffs: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "created_files": list(self.created_files),
            "modified_files": list(self.modified_files),
            "deleted_files": list(self.deleted_files),
            "diffs": self.diffs,
        }


class TransactionalWorkspace:
    """Manages transactional file modifications and change set diffing."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.change_set = ChangeSet()
        self._snapshots: Dict[str, FileSnapshot] = {}

    def normalize_rel_path(self, file_path: str) -> str:
        """Convert any file path into a clean relative path from workspace root."""
        norm = os.path.normpath(file_path)
        if os.path.isabs(norm):
            try:
                norm = os.path.relpath(norm, self.workspace_root)
            except ValueError:
                pass
        return norm.replace("\\", "/")

    def capture_pre_state(self, file_path: str) -> FileSnapshot:
        """Snapshot file state before a write/edit/delete operation."""
        rel_path = self.normalize_rel_path(file_path)
        abs_path = os.path.join(self.workspace_root, rel_path)

        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                h = hashlib.sha256(content.encode("utf-8")).hexdigest()
                snap = FileSnapshot(path=rel_path, exists=True, content=content, file_hash=h)
            except Exception:
                snap = FileSnapshot(path=rel_path, exists=True, content="", file_hash="")
        else:
            snap = FileSnapshot(path=rel_path, exists=False, content=None, file_hash=None)

        self._snapshots[rel_path] = snap
        return snap

    def capture_post_state(self, file_path: str, pre_snap: Optional[FileSnapshot] = None) -> Optional[str]:
        """Capture post-modification file state, generate diff, and update change set."""
        rel_path = self.normalize_rel_path(file_path)
        abs_path = os.path.join(self.workspace_root, rel_path)

        if not pre_snap:
            pre_snap = self._snapshots.get(rel_path) or FileSnapshot(path=rel_path, exists=False)

        post_exists = os.path.exists(abs_path) and os.path.isfile(abs_path)
        post_content: Optional[str] = None

        if post_exists:
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    post_content = f.read()
            except Exception:
                post_content = ""

        diff_text = ""

        if not pre_snap.exists and post_exists:
            # File Created
            self.change_set.created_files.add(rel_path)
            lines = (post_content or "").splitlines(keepends=True)
            diff_lines = difflib.unified_diff([], lines, fromfile="/dev/null", tofile=f"b/{rel_path}")
            diff_text = "".join(diff_lines)
            self.change_set.diffs[rel_path] = diff_text

        elif pre_snap.exists and not post_exists:
            # File Deleted
            self.change_set.deleted_files.add(rel_path)
            lines = (pre_snap.content or "").splitlines(keepends=True)
            diff_lines = difflib.unified_diff(lines, [], fromfile=f"a/{rel_path}", tofile="/dev/null")
            diff_text = "".join(diff_lines)
            self.change_set.diffs[rel_path] = diff_text

        elif pre_snap.exists and post_exists:
            # File Modified
            if pre_snap.content != post_content:
                self.change_set.modified_files.add(rel_path)
                pre_lines = (pre_snap.content or "").splitlines(keepends=True)
                post_lines = (post_content or "").splitlines(keepends=True)
                diff_lines = difflib.unified_diff(pre_lines, post_lines, fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}")
                diff_text = "".join(diff_lines)
                self.change_set.diffs[rel_path] = diff_text

        return diff_text
