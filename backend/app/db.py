from __future__ import annotations
import logging
import datetime
import os
from typing import Any, Optional

from fastapi import HTTPException
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
    import sys
    
    # 1. Run migrations if in dev environment
    if settings.ENVIRONMENT != "production":
        if getattr(sys, 'frozen', False):
            # When frozen (in PyInstaller), we cannot run 'sys.executable -m alembic'
            # Instead, we ensure all database tables are created using SQLAlchemy Base metadata.
            from backend.app.infrastructure.database.models import Base
            from backend.app.infrastructure.database.connection import engine
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables initialized successfully via SQLAlchemy Base metadata.")
            except Exception as e:
                logger.error(f"Failed to initialize database tables via SQLAlchemy metadata: {e}")
        else:
            # Running in standard Python development mode, use Alembic CLI via subprocess
            try:
                import subprocess
                import asyncio
                
                def run_alembic():
                    # Run the alembic CLI as a subprocess to avoid event loop nesting deadlocks
                    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    logger.info("Alembic migrations completed successfully.")
                    if result.stdout:
                        logger.debug(f"Alembic stdout: {result.stdout.strip()}")

                await asyncio.to_thread(run_alembic)
            except Exception as e:
                logger.warning(f"Initial Alembic migration check/run failed or table already exists: {e}")
                # Self-healing: if migrations fail (e.g. because tables already exist but version is unstamped),
                # we stamp the database to head so uvicorn can proceed.
                try:
                    def stamp_alembic():
                        cmd = [sys.executable, "-m", "alembic", "stamp", "head"]
                        subprocess.run(cmd, capture_output=True, check=True)
                    await asyncio.to_thread(stamp_alembic)
                    logger.info("Stamped alembic migration to head after initial check/run failure.")
                except Exception as stamp_err:
                    logger.error(f"Failed to stamp alembic to head: {stamp_err}")

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

async def get_fallback_session_id(
    workspace_root: Optional[str] = None,
    org_id: str = "default-org",
    user_id: Optional[str] = None,
) -> str:
    """Return the most recently updated session, optionally filtered by workspace, tenant, and user."""
    async with async_session() as db:
        ws_repo = WorkspaceRepository(db)
        conv_repo = ConversationRepository(db)

        target_ws_id = "default-workspace"
        if workspace_root:
            ws = await ws_repo.get_by_root(org_id, workspace_root)
            if ws:
                target_ws_id = ws.id

        stmt = select(SessionModel).where(
            SessionModel.organization_id == org_id,
            SessionModel.workspace_id == target_ws_id,
        )
        if user_id:
            stmt = stmt.where(SessionModel.user_id == user_id)
        stmt = stmt.order_by(SessionModel.updated_at.desc())
        res = await db.execute(stmt)
        conv = res.scalars().first()
        if conv:
            return conv.id
        return "default-session"


async def resolve_session_for_identity(
    session_id: str,
    *,
    request: Optional[Any] = None,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> SessionModel:
    """Validate a session belongs to the authenticated user and tenant."""
    from backend.app.config import settings
    is_prod_server = (settings.ENVIRONMENT.lower() == "production" and settings.MODE == "server")

    async with async_session() as db:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        res = await db.execute(stmt)
        session = res.scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        identity = getattr(request.state, "identity", None) if request else None
        if identity is not None:
            org_id = org_id or getattr(getattr(identity, "tenant", None), "tenant_id", None)
            user_id = user_id or getattr(identity, "user_id", None)

        if org_id and session.organization_id and session.organization_id != org_id:
            if is_prod_server or (org_id != "default-org" and session.organization_id != "default-org"):
                raise HTTPException(status_code=403, detail="Forbidden: session is not in your tenant")

        if user_id and session.user_id and session.user_id != user_id:
            if is_prod_server or (user_id != "default-user" and session.user_id != "default-user"):
                raise HTTPException(status_code=403, detail="Forbidden: session does not belong to you")

        return session

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

