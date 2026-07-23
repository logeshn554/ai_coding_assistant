"""Codebase search helper for agent tool dispatch."""

from __future__ import annotations

import json
from typing import Any, Dict

from ..async_files import async_search_workspace_codebase


async def search_codebase(session: Any, args: Dict[str, Any]) -> str:
    """Search the workspace for a symbol or pattern.

    Args:
        session: Active AgentSession providing workspace_root.
        args: Tool arguments; uses ``query``.

    Returns:
        JSON string of search hits.
    """
    query = args.get("query", "")
    results = await async_search_workspace_codebase(session.workspace_root, query)
    return json.dumps(results, indent=2)
