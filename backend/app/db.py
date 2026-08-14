from __future__ import annotations
import logging
import datetime
import os
from typing import Any, Optional

from sqlalchemy import select, delete
from backend.app.config import settings
from backend.app.infrastructure.database.connection import async_session_factory as async_session
from backend.app.infrastructure.database.models import Conversation as SessionModel
from backend.app.infrastructure.database.models import Message as MessageModel
from backend.app.infrastructure.database.repositories import (
    OrganizationRepository, UserRepository, WorkspaceRepository, ConversationRepository
)

logger = logging.getLogger("devpilot.db")

async def init_db() -> None:
    """Create tables, migrate columns, and seed a default session if empty."""
    from backend.app.config import settings
    # 1. Run migrations if in dev environment
    if settings.ENVIRONMENT != "production":
        import alembic.config
        import alembic.command
        try:
            alembic_cfg = alembic.config.Config("alembic.ini")
            import asyncio
            await asyncio.to_thread(alembic.command.upgrade, alembic_cfg, "head")
        except Exception as e:
            logger.error(f"Failed to run programmatic Alembic migrations: {e}")

    # 1b. Safe schema migration — add new columns if absent (SQLite compatible)
    from sqlalchemy import text
    from backend.app.infrastructure.database.connection import engine
    _new_agent_run_cols = [
        ("workspace_root", "VARCHAR(1024)"),
        ("profile_name", "VARCHAR(255)"),
    ]
    async with engine.begin() as conn:
        # Get existing columns via PRAGMA
        result = await conn.execute(text("PRAGMA table_info(agent_runs)"))
        existing_cols = {row[1] for row in result.fetchall()}
        for col_name, col_type in _new_agent_run_cols:
            if col_name not in existing_cols:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE agent_runs ADD COLUMN {col_name} {col_type}")
                    )
                    logger.info(f"Schema migration: added column agent_runs.{col_name}")
                except Exception as e:
                    logger.warning(f"Could not add column agent_runs.{col_name}: {e}")

    # 2. Run data migration helper
    from backend.app.infrastructure.database.migration_helper import import_legacy_data
    async with async_session() as db:
        await import_legacy_data(db)

        # 3. Seed defaults
        org_repo = OrganizationRepository(db)
        user_repo = UserRepository(db)
        ws_repo = WorkspaceRepository(db)
        conv_repo = ConversationRepository(db)

        org = await org_repo.get_by_id("default-org")
        if not org:
            org = await org_repo.create("Default Organization")
            org.id = "default-org"

        user = await user_repo.get_by_id("default-user")
        if not user:
            user = await user_repo.create("developer@devpilot.local", "Default Developer", "nopassword")
            user.id = "default-user"

        ws = await ws_repo.get_by_root("default-org", "")
        if not ws:
            from backend.app.infrastructure.database.models import Project
            proj_res = await db.execute(select(Project).where(Project.name == "Default Project"))
            proj = proj_res.scalars().first()
            if not proj:
                proj = Project(organization_id="default-org", name="Default Project")
                db.add(proj)
                await db.flush()
            ws = await ws_repo.create("default-org", proj.id, "Default Workspace", "")
            ws.id = "default-workspace"

        conv = await conv_repo.get_conversation("default-org", "default-session")
        if not conv:
            await conv_repo.create("default-org", "default-user", ws.id, "Default Conversation", id="default-session")

        await db.commit()

async def get_fallback_session_id(workspace_root: Optional[str] = None, org_id: str = "default-org") -> str:
    """Return the most recently updated session, optionally filtered by workspace and tenant organization."""
    async with async_session() as db:
        ws_repo = WorkspaceRepository(db)
        conv_repo = ConversationRepository(db)

        target_ws_id = "default-workspace"
        if workspace_root:
            ws = await ws_repo.get_by_root(org_id, workspace_root)
            if ws:
                target_ws_id = ws.id

        conv = await conv_repo.get_last_for_workspace(org_id, target_ws_id)
        if conv:
            return conv.id
        return "default-session"

async def get_last_session_for_workspace(workspace_root: str, org_id: str = "default-org") -> Optional[SessionModel]:
    """Load the most recent session for a workspace root and organization."""
    async with async_session() as db:
        ws_repo = WorkspaceRepository(db)
        conv_repo = ConversationRepository(db)
        ws = await ws_repo.get_by_root(org_id, workspace_root)
        if ws:
            return await conv_repo.get_last_for_workspace(org_id, ws.id)
        return None

async def get_or_create_workspace(db, workspace_root: str = "", org_id: str = "default-org") -> str:
    """Helper to get or create a workspace entity for a workspace root and organization."""
    ws_repo = WorkspaceRepository(db)
    ws = await ws_repo.get_by_root(org_id, workspace_root or "")
    if not ws:
        from backend.app.infrastructure.database.models import Project
        proj_res = await db.execute(select(Project).where(Project.organization_id == org_id))
        proj = proj_res.scalars().first()
        if not proj:
            proj = Project(organization_id=org_id, name="Default Project")
            db.add(proj)
            await db.flush()
        ws = await ws_repo.create(org_id, proj.id, "Workspace", workspace_root or "")
        await db.flush()
    return ws.id

async def create_new_session_record(
    db,
    session_id: str,
    title: str = "New Chat",
    workspace_root: str = "",
    mode: str = "Ask",
    org_id: str = "default-org",
    user_id: str = "default-user"
) -> SessionModel:
    """Safely create a new session record satisfying all database constraints for the tenant."""
    ws_id = await get_or_create_workspace(db, workspace_root, org_id=org_id)
    conv = SessionModel(
        id=session_id,
        organization_id=org_id,
        user_id=user_id,
        workspace_id=ws_id,
        title=title or "New Chat",
        workspace_root=workspace_root or "",
        mode=mode or "Ask",
        messages_json="[]",
    )
    db.add(conv)
    return conv

def first_user_preview(messages: list[Any], max_len: int = 60) -> str:
    """Return a brief text preview of the first user message found."""
    for msg in messages:
        role = ""
        content = ""
        if isinstance(msg, dict):
            role = msg.get("role") or ""
            content = msg.get("content") or ""
        else:
            role = getattr(msg, "role", "")
            content = getattr(msg, "content", "")
            
        if role == "user" and content:
            return content[:max_len] + "..." if len(content) > max_len else content
    return ""

