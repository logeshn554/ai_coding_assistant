import logging
import os

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.infrastructure.database.models import (
    Conversation,
    Message,
    Organization,
    Project,
    User,
    Workspace,
)

logger = logging.getLogger("devpilot.infrastructure.database.migration_helper")

async def import_legacy_data(db: AsyncSession) -> None:
    """Migrates old SQLite columns/tables to the new PostgreSQL/SQLite normalized schema."""
    try:
        # Check if legacy 'sessions' table exists
        res = await db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"))
        if not res.scalar():
            return

        # Ensure default organization and user exist
        res_org = await db.execute(select(Organization).where(Organization.id == "default-org"))
        org = res_org.scalars().first()
        if not org:
            org = Organization(id="default-org", name="Default Organization")
            db.add(org)

        res_user = await db.execute(select(User).where(User.id == "default-user"))
        user = res_user.scalars().first()
        if not user:
            user = User(
                id="default-user",
                email="developer@devpilot.local",
                full_name="Default Developer",
                hashed_password="nopassword"
            )
            db.add(user)

        await db.flush()

        # Query legacy sessions
        try:
            old_sessions_res = await db.execute(
                text("SELECT id, title, workspace_root, created_at, updated_at FROM sessions")
            )
            old_sessions = old_sessions_res.fetchall()
        except Exception:
            old_sessions = []

        for row in old_sessions:
            s_id, s_title, s_root, s_created, s_updated = row

            # Verify if this conversation is already imported
            res_conv = await db.execute(select(Conversation).where(Conversation.id == s_id))
            if res_conv.scalars().first():
                continue

            # Map workspace_root to logical project/workspace
            root_path = s_root or "default-workspace"
            res_proj = await db.execute(select(Project).where(Project.name == "Default Project"))
            proj = res_proj.scalars().first()
            if not proj:
                proj = Project(organization_id=org.id, name="Default Project")
                db.add(proj)
                await db.flush()

            res_ws = await db.execute(select(Workspace).where(Workspace.root_identifier == root_path))
            ws = res_ws.scalars().first()
            if not ws:
                ws = Workspace(
                    organization_id=org.id,
                    project_id=proj.id,
                    name=os.path.basename(root_path) or "Workspace",
                    root_identifier=root_path
                )
                db.add(ws)
                await db.flush()

            # Create Conversation
            conv = Conversation(
                id=s_id,
                organization_id=org.id,
                user_id=user.id,
                workspace_id=ws.id,
                title=s_title,
                created_at=s_created,
                updated_at=s_updated
            )
            db.add(conv)

            # Fetch legacy messages
            try:
                old_msgs_res = await db.execute(
                    text("SELECT role, content, timestamp FROM messages WHERE session_id = :sid"),
                    {"sid": s_id}
                )
                old_msgs = old_msgs_res.fetchall()
            except Exception:
                old_msgs = []

            for idx, m_row in enumerate(old_msgs):
                m_role, m_content, m_time = m_row
                msg = Message(
                    conversation_id=s_id,
                    role=m_role,
                    content=m_content,
                    sequence=idx,
                    created_at=m_time
                )
                db.add(msg)

        await db.commit()
        logger.info("Successfully imported legacy SQLite session history into the normalized schema.")
    except Exception as e:
        logger.error(f"Failed to migrate legacy SQLite data: {e}")
