"""Agent memory persistence — workspace-scoped key/value facts for the AI.

Memories are injected into the agent system prompt each turn so the AI
can learn project-specific conventions, preferences, and facts.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from ..db import async_session
from ..state import workspace_state

logger = logging.getLogger("devpilot.memory")

router = APIRouter()


class MemoryItem(BaseModel):
    """A single agent memory entry."""

    key: str
    value: str
    workspace_root: str = ""
    updated_at: int  # Unix timestamp


class MemoryListResponse(BaseModel):
    memories: list[MemoryItem]


class UpsertMemoryRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., max_length=4096)
    workspace_root: Optional[str] = None


@router.get("/api/memory", response_model=MemoryListResponse)
async def list_memories(
    workspace: Optional[str] = None,
    limit: int = 20,
) -> MemoryListResponse:
    """Return the top ``limit`` agent memories for the current workspace."""
    root = (workspace or workspace_state.root or "").strip()
    from ..db import MemoryModel

    async with async_session() as db:
        stmt = (
            select(MemoryModel)
            .where(MemoryModel.workspace_root == root)
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.scalars().all()

    memories = [
        MemoryItem(
            key=m.key,
            value=m.value,
            workspace_root=m.workspace_root or "",
            updated_at=int(m.updated_at.timestamp()) if m.updated_at else 0,
        )
        for m in rows
    ]
    return MemoryListResponse(memories=memories)


@router.put("/api/memory/{key}")
async def upsert_memory(key: str, req: UpsertMemoryRequest) -> dict:
    """Create or update a memory entry."""
    from ..db import MemoryModel

    root = (req.workspace_root or workspace_state.root or "").strip()
    async with async_session() as db:
        stmt = select(MemoryModel).where(
            MemoryModel.key == key,
            MemoryModel.workspace_root == root,
        )
        res = await db.execute(stmt)
        mem = res.scalar()
        if mem is None:
            mem = MemoryModel(key=key, value=req.value, workspace_root=root)
            db.add(mem)
        else:
            mem.value = req.value
        mem.updated_at = datetime.datetime.utcnow()
        await db.commit()
    return {"success": True, "key": key}


@router.delete("/api/memory/{key}")
async def delete_memory(key: str, workspace: Optional[str] = None) -> dict:
    """Delete a memory entry by key."""
    from ..db import MemoryModel

    root = (workspace or workspace_state.root or "").strip()
    async with async_session() as db:
        await db.execute(
            delete(MemoryModel).where(
                MemoryModel.key == key,
                MemoryModel.workspace_root == root,
            )
        )
        await db.commit()
    return {"success": True}


@router.delete("/api/memory")
async def clear_all_memories(workspace: Optional[str] = None) -> dict:
    """Delete ALL memories for the given workspace."""
    from ..db import MemoryModel

    root = (workspace or workspace_state.root or "").strip()
    async with async_session() as db:
        await db.execute(
            delete(MemoryModel).where(MemoryModel.workspace_root == root)
        )
        await db.commit()
    return {"success": True}
