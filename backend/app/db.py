"""Async SQLite persistence for DevPilot chat sessions and messages."""

from __future__ import annotations

import datetime
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

logger = logging.getLogger("devpilot.db")

DB_DIR = Path.home() / ".devpilot"
DB_FILE = DB_DIR / "history.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"

DB_DIR.mkdir(parents=True, exist_ok=True)

Base = declarative_base()


class SessionModel(Base):
    """A chat session scoped to a workspace."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    workspace_root = Column(String(1024), nullable=True, default="")
    mode = Column(String(32), nullable=True, default="Ask")
    messages_json = Column(Text, nullable=True, default="[]")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    messages = relationship(
        "MessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ChatSessionModel(Base):
    """Chat session table for persistent session history across restarts."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(1024), nullable=True, default="")
    title = Column(String(255), nullable=False)
    messages = Column(Text, nullable=True, default="[]")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )



class MessageModel(Base):
    """A single message belonging to a chat session."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("SessionModel", back_populates="messages")


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


class MemoryModel(Base):
    """Workspace-scoped agent memory entry (key/value fact store)."""

    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_root = Column(String(1024), nullable=False, default="", index=True)
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


async def _ensure_session_columns(conn: Any) -> None:
    """Add workspace_root / mode / messages_json if missing (SQLite ALTER)."""
    result = await conn.execute(text("PRAGMA table_info(sessions)"))
    rows = result.fetchall()
    existing = {row[1] for row in rows}

    alterations: list[tuple[str, str]] = [
        ("workspace_root", "ALTER TABLE sessions ADD COLUMN workspace_root VARCHAR(1024) DEFAULT ''"),
        ("mode", "ALTER TABLE sessions ADD COLUMN mode VARCHAR(32) DEFAULT 'Ask'"),
        ("messages_json", "ALTER TABLE sessions ADD COLUMN messages_json TEXT DEFAULT '[]'"),
    ]
    for col_name, ddl in alterations:
        if col_name not in existing:
            await conn.execute(text(ddl))
            logger.info("Migrated sessions table: added column %s", col_name)


async def init_db() -> None:
    """Create tables, migrate columns, and seed a default session if empty."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_session_columns(conn)
    await migrate_legacy_history()

    async with async_session() as db:
        res = await db.execute(select(SessionModel))
        any_session = res.scalars().first()
        if not any_session:
            default_session = SessionModel(
                id="default-session",
                title="Default Conversation",
                workspace_root="",
                mode="Ask",
                messages_json="[]",
            )
            db.add(default_session)
            await db.commit()


async def get_fallback_session_id(workspace_root: Optional[str] = None) -> str:
    """Return the most recently updated session, optionally filtered by workspace."""
    async with async_session() as db:
        stmt = select(SessionModel).order_by(SessionModel.updated_at.desc())
        if workspace_root:
            stmt = stmt.where(SessionModel.workspace_root == workspace_root)
        res = await db.execute(stmt)
        last_session = res.scalars().first()
        if last_session:
            return last_session.id
        if workspace_root:
            # Fall back to any session if none match this workspace
            res_any = await db.execute(
                select(SessionModel).order_by(SessionModel.updated_at.desc())
            )
            any_session = res_any.scalars().first()
            if any_session:
                return any_session.id
        return "default-session"


async def get_last_session_for_workspace(workspace_root: str) -> Optional[SessionModel]:
    """Load the most recent session for a workspace root."""
    async with async_session() as db:
        stmt = (
            select(SessionModel)
            .where(SessionModel.workspace_root == workspace_root)
            .order_by(SessionModel.updated_at.desc())
        )
        res = await db.execute(stmt)
        return res.scalars().first()


def truncate_preview(text: str, limit: int = 60) -> str:
    """Truncate text to ``limit`` chars for UI previews."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def first_user_preview(messages: list[dict[str, Any]], limit: int = 60) -> str:
    """Return a truncated preview of the first user message."""
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            return truncate_preview(str(content), limit)
    return "(no messages)"


async def migrate_legacy_history() -> None:
    """One-shot migration from ~/.devpilot/chat_sessions.json into SQLite."""
    legacy_file = DB_DIR / "chat_sessions.json"
    if not legacy_file.exists():
        return
    try:
        with open(legacy_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sessions_dict = data.get("sessions", {})
        async with async_session() as db:
            for s_id, s in sessions_dict.items():
                stmt = select(SessionModel).where(SessionModel.id == s_id)
                res = await db.execute(stmt)
                existing = res.scalar()
                if existing:
                    continue
                title = s.get("title", "Conversation")
                try:
                    c_at = datetime.datetime.utcfromtimestamp(
                        s.get("created_at", time.time())
                    )
                except (TypeError, ValueError, OSError):
                    c_at = datetime.datetime.utcnow()
                try:
                    u_at = datetime.datetime.utcfromtimestamp(
                        s.get("updated_at", time.time())
                    )
                except (TypeError, ValueError, OSError):
                    u_at = datetime.datetime.utcnow()

                msgs = s.get("messages", [])
                db_sess = SessionModel(
                    id=s_id,
                    title=title,
                    created_at=c_at,
                    updated_at=u_at,
                    workspace_root=s.get("workspace_root", ""),
                    mode=s.get("mode", "Ask"),
                    messages_json=json.dumps(msgs),
                )
                db.add(db_sess)

                for m in msgs:
                    m_role = m.get("role", "user")
                    m_content = m.get("content", "")
                    if isinstance(m_content, (dict, list)):
                        m_content = json.dumps(m_content)
                    try:
                        m_time = datetime.datetime.utcfromtimestamp(
                            m.get("timestamp", time.time())
                        )
                    except (TypeError, ValueError, OSError):
                        m_time = datetime.datetime.utcnow()
                    db_msg = MessageModel(
                        session_id=s_id,
                        role=m_role,
                        content=m_content,
                        timestamp=m_time,
                    )
                    db.add(db_msg)
            await db.commit()

        legacy_file.rename(legacy_file.with_name("chat_sessions.json.bak"))
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to migrate legacy history: %s", e)
