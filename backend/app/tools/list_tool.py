"""List Tool - lists files and directories in the workspace.

Exposes list_directory(session, args) as the agent-facing async function.
Supports both shallow (default) and recursive tree listing so the agent can
understand large projects with many folders in a single tool call.
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..async_files import async_list_workspace_dir

_EXCLUDE = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    "dist", "build", ".loopix", ".cache", ".mypy_cache",
}

MAX_ENTRIES = 2000


def _recursive_tree(root: str, rel_base: str, depth: int, max_depth: int, entries: list[dict]) -> None:
    if depth > max_depth or len(entries) >= MAX_ENTRIES:
        return
    try:
        scan_path = os.path.join(root, rel_base) if rel_base else root
        with os.scandir(scan_path) as it:
            for entry in sorted(it, key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())):
                if entry.name in _EXCLUDE or entry.name.startswith("."):
                    continue
                rel_path = (rel_base + "/" + entry.name).lstrip("/")
                is_dir = entry.is_dir(follow_symlinks=False)
                try:
                    size = 0 if is_dir else entry.stat().st_size
                    mtime = entry.stat().st_mtime
                except OSError:
                    size, mtime = 0, 0.0
                node = {"name": entry.name, "path": rel_path, "is_dir": is_dir, "size": size, "mtime": mtime}
                if is_dir:
                    try:
                        node["child_count"] = sum(1 for _ in os.scandir(entry.path) if _.name not in _EXCLUDE)
                    except OSError:
                        node["child_count"] = 0
                entries.append(node)
                if len(entries) >= MAX_ENTRIES:
                    return
                if is_dir:
                    _recursive_tree(root, rel_path, depth + 1, max_depth, entries)
    except PermissionError:
        pass


async def list_directory(session: Any, args: dict[str, Any]) -> str:
    path = args.get("path") or args.get("dir") or args.get("directory") or args.get("folder") or ""
    recursive = bool(args.get("recursive", False))
    max_depth = min(int(args.get("depth") or 4), 10)
    workspace_root = getattr(session, "workspace_root", ".")

    if not recursive:
        items = await async_list_workspace_dir(workspace_root, path)
        return json.dumps(items, indent=2)

    entries: list[dict] = []
    base_abs = os.path.join(workspace_root, path.lstrip("/\\")) if path else workspace_root
    if not os.path.isdir(base_abs):
        return json.dumps({"error": f"Directory '{path}' not found."})

    _recursive_tree(workspace_root, path.lstrip("/\\"), 0, max_depth, entries)
    note = f"Capped at {MAX_ENTRIES} entries. Use path/depth to narrow." if len(entries) >= MAX_ENTRIES else ""
    return json.dumps({"entries": entries, "total": len(entries), "note": note}, indent=2)
