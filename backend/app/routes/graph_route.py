import asyncio
import os
from fastapi import APIRouter, HTTPException
from ..state import workspace_state
from ..workspace_graph import build_workspace_graph

router = APIRouter()


@router.get("/api/workspace/graph")
async def get_workspace_graph():
    """
    Returns the node/edge dependency graph for the current workspace root (non-blocking).
    """
    root = (workspace_state.root or "").strip()
    if not root or not os.path.isdir(root):
        return {
            "nodes": [],
            "edges": [],
            "circular_imports": [],
            "summary": {"total_nodes": 0, "total_edges": 0, "circular_count": 0}
        }

    graph = await asyncio.to_thread(build_workspace_graph, root)
    return graph

