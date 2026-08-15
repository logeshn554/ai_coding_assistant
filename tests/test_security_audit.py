import pytest
import os
import tempfile
import json
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from backend.app.agent.security.secure_fs import SecureFileSystem
from backend.app.routes.profiles import validate_provider_url
from backend.app.state import create_ws_ticket, verify_ws_ticket
from backend.app.config import settings
from backend.app.gateway.auth import AuthIdentity, AuthMethod, TenantContext
from backend.app.infrastructure.database.connection import async_session_factory
from backend.app.infrastructure.database.models import Organization, Project, User, Workspace, Conversation


@pytest.mark.asyncio
async def test_fallback_session_is_user_scoped():
    u_id = uuid.uuid4().hex[:8]
    org_id = f"tenant-abc-{u_id}"
    user_a_id = f"user-a-{u_id}"
    user_b_id = f"user-b-{u_id}"
    ws_root = f"/tmp/workspace-1-{u_id}"
    conv_a_id = f"conv-user-a-{u_id}"
    conv_b_id = f"conv-user-b-{u_id}"

    async with async_session_factory() as db:
        org = Organization(id=org_id, name="Tenant ABC")
        user_a = User(id=user_a_id, email=f"a_{u_id}@example.com", full_name="User A", hashed_password="x")
        user_b = User(id=user_b_id, email=f"b_{u_id}@example.com", full_name="User B", hashed_password="x")
        project = Project(id=f"project-1-{u_id}", organization_id=org.id, name="Project 1")
        workspace = Workspace(
            id=f"workspace-1-{u_id}",
            organization_id=org.id,
            project_id=project.id,
            name="Workspace 1",
            root_identifier=ws_root,
        )
        conv_a = Conversation(
            id=conv_a_id,
            organization_id=org.id,
            user_id=user_a.id,
            workspace_id=workspace.id,
            title="User A Session",
            workspace_root=ws_root,
        )
        conv_b = Conversation(
            id=conv_b_id,
            organization_id=org.id,
            user_id=user_b.id,
            workspace_id=workspace.id,
            title="User B Session",
            workspace_root=ws_root,
        )
        db.add_all([org, user_a, user_b, project, workspace, conv_a, conv_b])
        await db.commit()

        result = await __import__("backend.app.db", fromlist=["get_fallback_session_id"]).get_fallback_session_id(
            ws_root,
            org_id=org.id,
            user_id=user_a.id,
        )
        assert result == conv_a_id


@pytest.mark.asyncio
async def test_session_access_is_enforced_by_user_and_tenant():
    u_id = uuid.uuid4().hex[:8]
    org_id = f"tenant-xyz-{u_id}"
    user_a_id = f"user-sec-a-{u_id}"
    user_b_id = f"user-sec-b-{u_id}"
    ws_root = f"/tmp/workspace-2-{u_id}"
    conv_id = f"conv-private-{u_id}"

    async with async_session_factory() as db:
        org = Organization(id=org_id, name="Tenant XYZ")
        user_a = User(id=user_a_id, email=f"a2_{u_id}@example.com", full_name="User A", hashed_password="x")
        project = Project(id=f"project-2-{u_id}", organization_id=org.id, name="Project 2")
        workspace = Workspace(
            id=f"workspace-2-{u_id}",
            organization_id=org.id,
            project_id=project.id,
            name="Workspace 2",
            root_identifier=ws_root,
        )
        conv = Conversation(
            id=conv_id,
            organization_id=org.id,
            user_id=user_a.id,
            workspace_id=workspace.id,
            title="Private Session",
            workspace_root=ws_root,
        )
        db.add_all([org, user_a, project, workspace, conv])
        await db.commit()

        request = MagicMock()
        request.state.identity = AuthIdentity(
            user_id=user_b_id,
            auth_method=AuthMethod.JWT,
            tenant=TenantContext(tenant_id=org_id),
            roles=["developer"],
            permissions=["workspace:read"],
        )

        with pytest.raises(HTTPException) as exc:
            await __import__("backend.app.db", fromlist=["resolve_session_for_identity"]).resolve_session_for_identity(
                conv_id,
                request=request,
            )
        assert exc.value.status_code == 403


def test_validate_provider_url_ssrf_blocking(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "MODE", "server")

    # Localhost / Loopback must be rejected in production server mode
    with pytest.raises(HTTPException) as exc1:
        validate_provider_url("http://127.0.0.1:8000/v1")
    assert exc1.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        validate_provider_url("http://localhost:11434/v1")
    assert exc2.value.status_code == 400

    # Cloud metadata endpoint must be rejected
    with pytest.raises(HTTPException) as exc3:
        validate_provider_url("http://169.254.169.254/latest/meta-data")
    assert exc3.value.status_code == 400

    # Public valid URLs should pass
    valid_url = "https://api.openai.com/v1"
    assert validate_provider_url(valid_url) == valid_url


def test_secure_filesystem_traversal_prevention():
    with tempfile.TemporaryDirectory() as tmpdir:
        sfs = SecureFileSystem(tmpdir)
        
        # Safe relative paths should resolve inside tmpdir
        safe_p = sfs.resolve_safe_path("src/app.py")
        assert safe_p.startswith(os.path.realpath(tmpdir))

        # Path traversal with ../ should raise PermissionError
        with pytest.raises(PermissionError):
            sfs.resolve_safe_path("../../etc/passwd")

        # Secret file read protection
        sfs.write_text("config.json", '{"key": "value"}')
        assert sfs.read_text("config.json") == '{"key": "value"}'

        with pytest.raises(PermissionError):
            sfs.write_text(".env", "SECRET=123")


def test_websocket_ticket_tenant_identity_binding():
    # Ticket bound to custom tenant and user identity
    ticket = create_ws_ticket(user_id="user_123", tenant_id="org_abc", workspace_id="ws_999")
    assert isinstance(ticket, str) and len(ticket) > 20

    # Verify and consume the ticket
    identity = verify_ws_ticket(ticket)
    assert identity is not None
    assert identity["user_id"] == "user_123"
    assert identity["tenant_id"] == "org_abc"
    assert identity["workspace_id"] == "ws_999"

    # Ticket should be single-use (already popped)
    assert verify_ws_ticket(ticket) is None
