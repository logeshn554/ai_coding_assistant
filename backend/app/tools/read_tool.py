"""Read Tool – reads a file from the workspace and returns its contents.

Exposes ``read_file(session, args)`` as the agent-facing async function.
"""
from __future__ import annotations

from typing import Any, Dict

from ..async_files import async_read_workspace_file


async def read_file(session: Any, args: Dict[str, Any]) -> str:
    """Read a file relative to the workspace root.

    Args:
        session: Active AgentSession providing workspace_root.
        args:
            path (str, required): Relative path of the file to read.

    Returns:
        File contents as a string.
    """
    path = (
        args.get("path")
        or args.get("file")
        or args.get("filepath")
        or args.get("filename")
        or ""
    )
    return await async_read_workspace_file(session.workspace_root, path)
