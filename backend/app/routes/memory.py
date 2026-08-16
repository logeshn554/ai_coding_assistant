
from fastapi import APIRouter
from pydantic import BaseModel

from ..memory_manager import MemoryManager, global_memory_manager
from ..state import workspace_state

router = APIRouter()


class AddRuleRequest(BaseModel):
    title: str
    content: str
    category: str | None = "convention"


class SearchMemoryRequest(BaseModel):
    query: str


@router.get("/api/memory")
async def get_memory():
    """
    Returns persistent project memory from .antigravity/memory.json.
    """
    root = (workspace_state.root or "").strip()
    mgr = MemoryManager(root) if root else global_memory_manager
    return mgr.get_memory()


@router.post("/api/memory")
async def add_memory_rule(req: AddRuleRequest):
    """
    Adds a new rule / convention to persistent memory.
    """
    root = (workspace_state.root or "").strip()
    mgr = MemoryManager(root) if root else global_memory_manager
    new_item = mgr.add_convention(req.title, req.content, req.category or "convention")
    return {"success": True, "rule": new_item}


@router.post("/api/memory/toggle/{rule_id}")
async def toggle_memory_rule(rule_id: str):
    """
    Toggles an existing rule.
    """
    root = (workspace_state.root or "").strip()
    mgr = MemoryManager(root) if root else global_memory_manager
    success = mgr.toggle_convention(rule_id)
    return {"success": success}


@router.delete("/api/memory/{rule_id}")
async def delete_memory_rule(rule_id: str):
    """
    Deletes a rule from persistent memory.
    """
    root = (workspace_state.root or "").strip()
    mgr = MemoryManager(root) if root else global_memory_manager
    success = mgr.delete_convention(rule_id)
    return {"success": success}


@router.post("/api/memory/search")
async def search_memory(req: SearchMemoryRequest):
    """
    Searches persistent project memory.
    """
    root = (workspace_state.root or "").strip()
    mgr = MemoryManager(root) if root else global_memory_manager
    results = mgr.search_memory(req.query)
    return {"results": results}
