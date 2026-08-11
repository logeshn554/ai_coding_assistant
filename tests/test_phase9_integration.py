import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.app.session.agent_session import AgentSession
from backend.app.orchestrator import AgentOrchestrator


@pytest.mark.asyncio
async def test_agent_mode_routes_to_orchestrator():
    """Verify that agent mode calls orchestrator.run_task directly."""
    send_ws_mock = AsyncMock()
    profile = {
        "api_key": "test-key",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o-mini",
        "api_format": "openai",
    }
    
    session = AgentSession(
        workspace_root=".",
        profile=profile,
        send_ws_message=send_ws_mock,
        session_id="test_session"
    )
    
    # Mock orchestrator.run_task
    run_task_mock = AsyncMock(return_value="completed")
    session.orchestrator.run_task = run_task_mock
    
    # Call handle_user_message in Agent mode
    await session.handle_user_message("Fix authentication", mode="Agent", auto_apply=True)
    
    # Verify run_task was called with prompt
    run_task_mock.assert_called_once_with("Fix authentication", session)


@pytest.mark.asyncio
async def test_ask_mode_runs_direct_loop():
    """Verify that Ask mode uses direct LLM query and does not call orchestrator.run_task."""
    send_ws_mock = AsyncMock()
    profile = {
        "api_key": "test-key",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o-mini",
        "api_format": "openai",
    }
    
    session = AgentSession(
        workspace_root=".",
        profile=profile,
        send_ws_message=send_ws_mock,
        session_id="test_session"
    )
    
    # Mock orchestrator.run_task
    run_task_mock = AsyncMock()
    session.orchestrator.run_task = run_task_mock
    
    # Mock direct query stream
    session._stream_chat_wrapper = MagicMock()
    async def mock_stream(*args, **kwargs):
        yield {"type": "text", "content": "Direct response"}
    session._stream_chat_wrapper.return_value = mock_stream()
    
    # Call handle_user_message in Ask mode
    await session.handle_user_message("Hello", mode="Ask", auto_apply=False)
    
    # Verify run_task was not called
    run_task_mock.assert_not_called()
