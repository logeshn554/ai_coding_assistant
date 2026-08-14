import pytest
import os
import tempfile
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from backend.app.agent.security.secure_fs import SecureFileSystem
from backend.app.routes.profiles import validate_provider_url
from backend.app.state import create_ws_ticket, verify_ws_ticket
from backend.app.config import settings


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
