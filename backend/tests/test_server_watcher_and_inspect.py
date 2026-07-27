"""Tests for Dev-Server Visual + Runtime QA feature.

Covers:
- ServerWatcher pattern detection and debouncing
- browser_capture.capture_page with mocked Playwright (structured CaptureResult)
- /api/inspect endpoint rejecting non-localhost URLs (HTTP 400)
- Setting gate: auto_inspect_on_server_start default False / opt-in behavior
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.tools.browser_capture import CaptureResult, capture_page, is_localhost_url
from app.tools.server_watcher import ServerWatcher


# ===========================================================================
# 1. ServerWatcher Detection and Debounce Tests
# ===========================================================================
def test_server_watcher_detection_and_debounce():
    """ServerWatcher detects localhost URLs and debounces rapid successive logs."""
    watcher = ServerWatcher(debounce_interval=10.0)

    line1 = "  ➜  Local:   http://localhost:5173/"
    line2 = "  ➜  Network: use --host to expose"

    # First occurrence -> detected
    url1 = watcher.check_log_line(line1)
    assert url1 == "http://localhost:5173"

    # Rapid second occurrence -> debounced (returns None)
    url2 = watcher.check_log_line(line1)
    assert url2 is None

    # Irrelevant log line -> None
    url3 = watcher.check_log_line(line2)
    assert url3 is None


def test_server_watcher_extracts_uvicorn_and_webpack_lines():
    """ServerWatcher extracts URLs from Uvicorn, Webpack, and generic ready logs."""
    watcher = ServerWatcher(debounce_interval=1.0)

    url_uvicorn = watcher.extract_url("INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)")
    assert url_uvicorn == "http://127.0.0.1:8000"

    url_port = watcher.extract_url("Server started on port 3000")
    assert url_port == "http://localhost:3000"

    url_webpack = watcher.extract_url("webpack compiled successfully in 250ms")
    assert url_webpack == "http://localhost:5173"


# ===========================================================================
# 2. Localhost URL Guardrail Tests
# ===========================================================================
def test_is_localhost_url_accepts_valid_hosts():
    """is_localhost_url accepts localhost, 127.0.0.1, ::1, and 0.0.0.0."""
    assert is_localhost_url("http://localhost:5173") is True
    assert is_localhost_url("http://127.0.0.1:8000/api") is True
    assert is_localhost_url("http://[::1]:3000") is True


def test_is_localhost_url_rejects_external_hosts():
    """is_localhost_url raises ValueError for non-localhost domains and IPs."""
    with pytest.raises(ValueError, match="restricted to local dev servers"):
        is_localhost_url("https://google.com")

    with pytest.raises(ValueError, match="restricted to local dev servers"):
        is_localhost_url("http://192.168.1.50:8000")

    with pytest.raises(ValueError, match="restricted to local dev servers"):
        is_localhost_url("http://attacker.com/malicious")


# ===========================================================================
# 3. Playwright Capture Page Mocked Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_capture_page_returns_structured_capture_result(tmp_path):
    """capture_page returns structured CaptureResult with console/network events."""
    mock_console_msg = MagicMock()
    mock_console_msg.type = "error"
    mock_console_msg.text = "Uncaught TypeError: Cannot read properties of undefined"
    mock_console_msg.location = {"url": "http://localhost:5173/src/App.tsx", "lineNumber": 42, "columnNumber": 10}

    mock_response = MagicMock()
    mock_response.url = "http://localhost:5173/api/data"
    mock_response.status = 500
    mock_response.status_text = "Internal Server Error"
    mock_response.request.method = "GET"

    mock_page = AsyncMock()
    mock_page.title.return_value = "Test React App"
    mock_page.url = "http://localhost:5173/"
    mock_page.screenshot = AsyncMock()

    # Capture event listeners attached via page.on(...)
    listeners = {}

    def mock_on(event_name, handler):
        listeners[event_name] = handler

    mock_page.on = mock_on

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.close = AsyncMock()

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    async def mock_goto(url_arg, **kwargs):
        if "console" in listeners:
            listeners["console"](mock_console_msg)
        if "response" in listeners:
            listeners["response"](mock_response)

    mock_page.goto = AsyncMock(side_effect=mock_goto)

    class AsyncPlaywrightCM:
        async def __aenter__(self):
            return mock_playwright

        async def __aexit__(self, *args):
            pass

    with patch("app.tools.browser_capture.get_async_playwright", return_value=lambda: AsyncPlaywrightCM()):
        res: CaptureResult = await capture_page("http://localhost:5173", workspace_root=str(tmp_path))

    assert isinstance(res, CaptureResult)
    assert res.final_url == "http://localhost:5173/"
    assert res.page_title == "Test React App"
    assert len(res.console_messages) >= 1
    assert res.console_messages[0]["type"] == "error"
    assert "TypeError" in res.console_messages[0]["text"]
    assert len(res.failed_requests) >= 1
    assert res.failed_requests[0]["status"] == 500


# ===========================================================================
# 4. GET & POST /api/inspect Endpoint Tests
# ===========================================================================
def test_inspect_endpoint_refuses_non_localhost():
    """POST /api/inspect returns 400 Bad Request when passed external URL."""
    client = TestClient(app)
    res = client.post("/api/inspect", json={"url": "https://example.com"})
    assert res.status_code == 400
    data = res.json()
    assert "restricted to local dev servers" in data["detail"].lower()


@pytest.mark.asyncio
async def test_inspect_endpoint_executes_capture_and_enqueues(tmp_path):
    """POST /api/inspect captures page and enqueues synthetic turn for localhost."""
    mock_result = CaptureResult(
        screenshot_path="",
        console_messages=[{"type": "error", "text": "Failed to load resource"}],
        network_requests=[],
        failed_requests=[{"url": "http://localhost:5173/api/user", "status": 404}],
        page_title="My Dev App",
        final_url="http://localhost:5173",
    )

    client = TestClient(app)

    with patch("app.routes.inspect_route.capture_page", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = mock_result
        with patch("app.session.agent_session.AgentSession.enqueue_message", new_callable=AsyncMock) as mock_enqueue:
            res = client.post("/api/inspect", json={
                "url": "http://localhost:5173",
                "workspace_root": str(tmp_path),
            })

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["final_url"] == "http://localhost:5173"
    assert data["console_errors_count"] == 1
    assert data["failed_requests_count"] == 1


# ===========================================================================
# 5. Setting Gate Test: auto_inspect_on_server_start
# ===========================================================================
def test_setting_gate_auto_inspect_defaults_off():
    """auto_inspect_on_server_start defaults to False and respects gate."""
    from app.state import config_manager

    # Default is False
    assert config_manager.get_auto_inspect_on_server_start() is False

    watcher = ServerWatcher(debounce_interval=1.0)
    session = MagicMock()
    session.send_ws_message = AsyncMock()

    # With gate OFF
    with patch("app.state.config_manager.get_auto_inspect_on_server_start", return_value=False):
        url1 = watcher.check_log_line("Local: http://localhost:5173/", session=session)
        assert url1 == "http://localhost:5173"
        # Verify event was sent with auto_inspect=False
        session.send_ws_message.assert_called_once()
        evt = session.send_ws_message.call_args[0][0]
        assert evt["type"] == "server_detected"
        assert evt["auto_inspect"] is False

    # Reset and test with gate ON
    watcher.reset()
    session.send_ws_message.reset_mock()

    with patch("app.state.config_manager.get_auto_inspect_on_server_start", return_value=True):
        url2 = watcher.check_log_line("Local: http://localhost:5173/", session=session)
        assert url2 == "http://localhost:5173"
        session.send_ws_message.assert_called_once()
        evt = session.send_ws_message.call_args[0][0]
        assert evt["type"] == "server_detected"
        assert evt["auto_inspect"] is True
