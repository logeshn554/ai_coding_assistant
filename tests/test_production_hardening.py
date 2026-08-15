import pytest
from backend.app.config import Settings

def test_production_fails_on_sqlite():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///devpilot.db",
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "PostgreSQL" in str(excinfo.value)

def test_production_fails_on_debug():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            DEBUG=True,
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "DEBUG mode is forbidden" in str(excinfo.value)

def test_production_fails_on_disabled_sandbox():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            USE_SANDBOX=False,
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "Sandbox environment is mandatory" in str(excinfo.value)

def test_production_fails_on_wildcard_cors():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            USE_SANDBOX=True,
            CORS_ORIGINS=["*"],
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "Wildcard CORS origins are forbidden" in str(excinfo.value)

def test_production_succeeds_on_valid_setup():
    settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://user:pass@localhost/db",
        USE_SANDBOX=True,
        CORS_ORIGINS=["http://localhost:3000"],
        JWT_SECRET="super-secret-production-jwt-key-xyz"
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.DATABASE_URL == "postgresql://user:pass@localhost/db"


@pytest.mark.asyncio
async def test_production_sandbox_fails_closed_when_docker_unavailable(monkeypatch):
    from backend.app.config import settings
    from backend.app.utils import run_cmd_async
    import backend.app.tools.terminal_tool as tt

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "USE_SANDBOX", True)
    monkeypatch.setattr(tt, "_is_docker_available", lambda: False)

    with pytest.raises(RuntimeError) as excinfo:
        await run_cmd_async("echo 'secret'", cwd="/tmp")
    assert "Production Sandbox Unavailable" in str(excinfo.value) or "fail-closed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_active_process_fails_closed_in_production(monkeypatch):
    from backend.app.config import settings
    from backend.app.processes import ActiveProcess
    import backend.app.tools.terminal_tool as tt

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "USE_SANDBOX", True)
    monkeypatch.setattr(tt, "_is_docker_available", lambda: False)

    proc = ActiveProcess(command="npm start", cwd="/tmp")
    await proc.start()
    assert proc.status == "failed"
    assert any("Production Sandbox Unavailable" in line for line in proc.logs)


@pytest.mark.asyncio
async def test_save_history_to_db_idempotent():
    import uuid
    from backend.app.infrastructure.database.connection import async_session_factory
    from backend.app.infrastructure.database.models import Organization, Project, User, Workspace, Conversation, Message
    from backend.app.session.agent_session import AgentSession
    from sqlalchemy import select

    u_id = uuid.uuid4().hex[:8]
    session_id = f"test-idempotent-conv-{u_id}"
    org_id = f"org-idem-{u_id}"
    user_id = f"user-idem-{u_id}"
    ws_root = f"/tmp/idem-{u_id}"

    async with async_session_factory() as db:
        org = Organization(id=org_id, name="Idem Org")
        user = User(id=user_id, email=f"idem_{u_id}@example.com", full_name="Idem User", hashed_password="x")
        proj = Project(id=f"proj-idem-{u_id}", organization_id=org.id, name="Idem Proj")
        ws = Workspace(id=f"ws-idem-{u_id}", organization_id=org.id, project_id=proj.id, name="WS Idem", root_identifier=ws_root)
        conv = Conversation(id=session_id, organization_id=org.id, user_id=user.id, workspace_id=ws.id, title="Idem Session", workspace_root=ws_root)
        db.add_all([org, user, proj, ws, conv])
        await db.commit()

    agent_session = AgentSession(
        workspace_root=ws_root,
        profile={"model": "test"},
        send_ws_message=lambda msg: None,
        session_id=session_id,
    )
    agent_session.conversation_history = [
        {"role": "user", "content": "Hello 1"},
        {"role": "assistant", "content": "Hi 1"},
    ]
    # First save
    await agent_session.save_history_to_db()

    # Second save with same + new messages
    agent_session.conversation_history.append({"role": "user", "content": "Hello 2"})
    await agent_session.save_history_to_db()

    # Load from DB and verify exact count and sequence
    await agent_session.load_history_from_db()
    assert len(agent_session.conversation_history) == 3
    assert agent_session.conversation_history[0]["content"] == "Hello 1"
    assert agent_session.conversation_history[1]["content"] == "Hi 1"
    assert agent_session.conversation_history[2]["content"] == "Hello 2"

