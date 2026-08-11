"""
Change Detection Engine — Tracks workspace file modifications.

Combines filesystem metadata snapshots (mtime/size) and git diff/status checks
to ensure all modified, added, or deleted files are accurately captured,
even if edited via shell commands or external compilers.
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, Set

logger = logging.getLogger("agent_runtime.workspace.changes")


def get_workspace_snapshot(workspace_root: str) -> Dict[str, tuple[float, int]]:
    """Generate a snapshot of the workspace files mapping relative path -> (mtime, size)."""
    snapshot = {}
    skip_dirs = {".git", "node_modules", "__pycache__", "dist", "build", "venv", ".venv", ".pytest_cache"}
    
    abs_root = os.path.abspath(workspace_root)
    for root, dirs, files in os.walk(abs_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, abs_root).replace("\\", "/")
            try:
                stat = os.stat(full_path)
                snapshot[rel_path] = (stat.st_mtime, stat.st_size)
            except OSError:
                continue
    return snapshot


def compare_snapshots(before: Dict[str, tuple[float, int]], after: Dict[str, tuple[float, int]]) -> Set[str]:
    """Compare before and after snapshots to find modified, added, or deleted files."""
    changed = set()
    
    # 1. Added or modified files
    for path, meta in after.items():
        if path not in before:
            changed.add(path)
        else:
            before_mtime, before_size = before[path]
            after_mtime, after_size = meta
            if before_mtime != after_mtime or before_size != after_size:
                changed.add(path)
                
    # 2. Deleted files
    for path in before:
        if path not in after:
            changed.add(path)
            
    return changed


async def get_git_modified_files(workspace_root: str) -> Set[str]:
    """Execute git status to find modified/untracked files."""
    cmd = ["git", "status", "--porcelain", "--ignored=no"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace_root
        )
        stdout_bytes, _ = await proc.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        
        changed = set()
        if proc.returncode == 0 and stdout:
            for line in stdout.splitlines():
                if len(line) > 3:
                    # git status --porcelain formats as: " M path/to/file.py" or "?? path/to/file.py"
                    rel_path = line[3:].strip().replace("\\", "/")
                    # Strip quotes if present
                    if rel_path.startswith('"') and rel_path.endswith('"'):
                        rel_path = rel_path[1:-1]
                    changed.add(rel_path)
        return changed
    except Exception as e:
        logger.debug(f"Git status failed (expected if not a git repository): {e}")
        return set()


async def detect_changed_files(workspace_root: str, before_snapshot: Dict[str, tuple[float, int]]) -> list[str]:
    """Detect all changed files using both snapshot and git status queries."""
    after_snapshot = get_workspace_snapshot(workspace_root)
    snapshot_changes = compare_snapshots(before_snapshot, after_snapshot)
    
    # Combine with Git status check
    git_changes = await get_git_modified_files(workspace_root)
    
    all_changes = snapshot_changes.union(git_changes)
    return sorted(list(all_changes))
