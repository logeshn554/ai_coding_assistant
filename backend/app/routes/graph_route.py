import asyncio
import os
from fastapi import APIRouter, HTTPException
from ..state import workspace_state
from ..workspace_graph import build_workspace_graph, get_or_generate_node_summary

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
            "summary": {
                "total_nodes": 0,
                "total_edges": 0,
                "circular_count": 0,
                "total_files_found": 0,
                "truncated": False
            },
            "total_files_found": 0,
            "truncated": False
        }

    graph = await asyncio.to_thread(build_workspace_graph, root)
    return graph


@router.get("/api/workspace/graph/summary/{node_id}")
async def get_node_summary(node_id: str):
    """
    Lazily generates and caches a 1-2 sentence AI summary for a specific node in the workspace graph.
    """
    root = (workspace_state.root or "").strip()
    if not root or not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="Workspace root is invalid or not selected")

    res = await get_or_generate_node_summary(root, node_id)
    if "error" in res and res.get("summary") == "":
        raise HTTPException(status_code=404, detail=res["error"])

    return res
