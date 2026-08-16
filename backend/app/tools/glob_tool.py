"""Glob tool – pattern-based file discovery within the workspace.

Exposes ``glob_search(session, args)`` as the agent-facing async function.
Security: all results are constrained to workspace_root; paths that escape
via ``..`` traversal are silently filtered.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MAX_RESULTS = 500  # Hard cap to avoid flooding context


async def glob_search(session: Any, args: dict[str, Any]) -> str:
    """Find files matching a glob pattern inside the workspace.

    Args:
        session: Active AgentSession (provides workspace_root).
        args:
            pattern (str, required): Glob pattern relative to workspace root,
                e.g. ``**/*.py``, ``src/**/*.tsx``, ``*.json``.
            base_path (str, optional): Sub-directory to search within
                (relative to workspace root). Defaults to workspace root.

    Returns:
        Newline-separated list of matching relative paths, or a
        "no matches" message.
    """
    pattern: str = (args.get("pattern") or "").strip()
    if not pattern:
        return "Error: 'pattern' argument is required for glob_search."

    base_rel: str = (args.get("base_path") or ".").strip().lstrip("/\\")
    workspace_root = Path(getattr(session, "workspace_root", ".")).resolve()
    base_dir = (workspace_root / base_rel).resolve()

    # Security: base_dir must stay inside workspace
    try:
        base_dir.relative_to(workspace_root)
    except ValueError:
        return "Error: base_path escapes the workspace root."

    if not base_dir.is_dir():
        return f"Error: base_path '{base_rel}' is not a directory."

    try:
        matches = sorted(base_dir.glob(pattern))
    except Exception as exc:
        return f"Error executing glob '{pattern}': {exc}"

    # Filter: files only, no escape, skip common noise dirs
    _NOISE = {".git", "node_modules", "__pycache__", "venv", "dist", "build", ".devpilot"}

    results: list[str] = []
    for p in matches:
        try:
            resolved = p.resolve()
            # Must stay inside workspace
            resolved.relative_to(workspace_root)
        except (ValueError, OSError):
            continue
        # Skip paths that pass through noise directories
        parts = set(resolved.relative_to(workspace_root).parts)
        if parts & _NOISE:
            continue
        rel = str(resolved.relative_to(workspace_root)).replace(os.sep, "/")
        results.append(rel)
        if len(results) >= MAX_RESULTS:
            break

    if not results:
        return f"No files matched pattern '{pattern}' in '{base_rel}'."

    header = f"Found {len(results)} file(s) matching '{pattern}':\n"
    if len(results) >= MAX_RESULTS:
        header = f"Found {MAX_RESULTS}+ matches (capped). Refine your pattern.\n"
    return header + "\n".join(results)
