"""Session history REST API (workspace-scoped chat sessions)."""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..db import (
    MessageModel,
    SessionModel,
    async_session,
    first_user_preview,
)
from ..state import workspace_state

logger = logging.getLogger("devpilot.sessions")

router = APIRouter()


class TokenUsageDict(BaseModel):
    input: int = 0
    output: int = 0
    total: int = 0

class SessionSummary(BaseModel):
    """Summary row for the Session History UI matching Requirement 9."""

    id: str
    title: str
    workspace_root: str = ""
    mode: str = "Ask"
    provider: str = ""
    model: str = ""
    created_at: int
    updated_at: int
    message_count: int = 0
    first_user_message: str = ""
    tokenUsage: TokenUsageDict = Field(default_factory=TokenUsageDict)


class SessionListResponse(BaseModel):
    """Response for GET /api/sessions."""

    sessions: list[SessionSummary]
    active_session_id: Optional[str] = None


class MessageOut(BaseModel):
    """A single chat message."""

    role: str
    content: Any
    timestamp: int


class SessionMessagesResponse(BaseModel):
    """Response for GET /api/sessions/{id}/messages."""

    session_id: str
    messages: list[MessageOut]


def _message_payload(m: MessageModel) -> dict[str, Any]:
    content: Any = m.content
    try:
        content = json.loads(m.content)
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "role": m.role,
        "content": content,
        "timestamp": int(m.timestamp.timestamp()) if m.timestamp else 0,
    }


def _session_to_summary(s: SessionModel) -> SessionSummary:
    msgs = list(s.messages or [])
    payloads = [_message_payload(m) for m in msgs]
    preview = first_user_preview(payloads, 60)
    if preview == "(no messages)" and s.messages_json:
        try:
            cached = json.loads(s.messages_json or "[]")
            if isinstance(cached, list):
                preview = first_user_preview(cached, 60)
        except (json.JSONDecodeError, TypeError):
            pass
    inp = getattr(s, 'token_input', 0) or 0
    outp = getattr(s, 'token_output', 0) or 0
    tot = getattr(s, 'token_total', 0) or (inp + outp)
    return SessionSummary(
        id=s.id,
        title=s.title or "Conversation",
        workspace_root=s.workspace_root or "",
        mode=s.mode or "Ask",
        provider=getattr(s, 'provider', '') or '',
        model=getattr(s, 'model', '') or '',
        created_at=int(s.created_at.timestamp()) if s.created_at else 0,
        updated_at=int(s.updated_at.timestamp()) if s.updated_at else 0,
        message_count=len(msgs),
        first_user_message=preview,
        tokenUsage=TokenUsageDict(input=inp, output=outp, total=tot)
    )


@router.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(
    workspace: Optional[str] = Query(
        None, description="Filter by workspace root; defaults to current workspace"
    ),
) -> SessionListResponse:
    """List chat sessions, newest first, optionally filtered by workspace."""
    root = (workspace or workspace_state.root or "").strip()
    async with async_session() as db:
        stmt = select(SessionModel).options(selectinload(SessionModel.messages)).order_by(SessionModel.updated_at.desc())
        res = await db.execute(stmt)
        sessions = list(res.scalars().all())

        if root:
            scoped = [s for s in sessions if (s.workspace_root or "") == root]
            # If nothing matches yet, show all so the UI is not empty
            sessions = scoped if scoped else sessions

        summaries = [_session_to_summary(s) for s in sessions]
        active_id = summaries[0].id if summaries else None
        return SessionListResponse(sessions=summaries, active_session_id=active_id)


@router.get(
    "/api/sessions/{session_id}/messages",
    response_model=SessionMessagesResponse,
)
async def get_session_messages(session_id: str) -> SessionMessagesResponse:
    """Return all messages for a session."""
    async with async_session() as db:
        stmt = select(SessionModel).options(selectinload(SessionModel.messages)).where(SessionModel.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = [_message_payload(m) for m in (session.messages or [])]
        return SessionMessagesResponse(
            session_id=session_id,
            messages=[MessageOut(**m) for m in messages],
        )


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session from history."""
    async with async_session() as db:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar()
        if session:
            await db.delete(session)
            await db.commit()
    return {"success": True, "session_id": session_id}


async def touch_session_meta(
    session_id: str,
    *,
    workspace_root: Optional[str] = None,
    mode: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    title: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    token_input: Optional[int] = None,
    token_output: Optional[int] = None,
) -> None:
    """Update session metadata after a turn (workspace, mode, provider, model, tokens, JSON snapshot)."""
    async with async_session() as db:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar()
        if not session:
            session = SessionModel(
                id=session_id,
                title=title or "Conversation",
                workspace_root=workspace_root or "",
                mode=mode or "Ask",
                provider=provider or "",
                model=model or "",
            )
            db.add(session)

        if workspace_root is not None:
            session.workspace_root = workspace_root
        if mode is not None:
            session.mode = mode
        if title is not None:
            session.title = title
        if provider is not None:
            session.provider = provider
        if model is not None:
            session.model = model
        if token_input is not None:
            session.token_input = (getattr(session, 'token_input', 0) or 0) + token_input
        if token_output is not None:
            session.token_output = (getattr(session, 'token_output', 0) or 0) + token_output
            session.token_total = (session.token_input or 0) + (session.token_output or 0)
        if messages is not None:
            session.messages_json = json.dumps(messages)
        session.updated_at = datetime.datetime.utcnow()
        await db.commit()

