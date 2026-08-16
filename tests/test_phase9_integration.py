import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock
from backend.app.session.agent_session import AgentSession
from backend.app.orchestrator import AgentOrchestrator


@pytest.mark.asyncio
async def test_agent_mode_routes_to_orchestrator():
    """Verify that agent mode routes through unified AgentRuntime."""
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
    
    # Mock agent_runtime.run
    mock_res = MagicMock(
        changed_files={"created_files": [], "modified_files": [], "deleted_files": [], "diffs": {}},
        verification_status="NOT_RUN",
        state="COMPLETED",
        output="completed",
        errors=[]
    )
    run_mock = AsyncMock(return_value=mock_res)
    session.agent_runtime.run = run_mock
    
    # Call handle_user_message in Agent mode
    await session.handle_user_message("Fix authentication", mode="Agent", auto_apply=True)
    
    # Verify AgentRuntime.run was called
    run_mock.assert_called_once()
    assert run_mock.call_args.kwargs.get("task") == "Fix authentication"


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


@pytest.mark.asyncio
async def test_per_agent_profile_routing():
    """Verify that when a custom connection profile is mapped for a specific agent role,
    the router resolves it and overrides the default active profile.
    """
    from backend.app.config import config_manager
    from backend.app.adapters.router import ModelRouter
    
    # Configure custom mock profiles in ConfigManager
    profile_1 = {
        "id": "profile-active",
        "name": "Active Profile",
        "api_key": "active-api-key",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o-mini",
        "api_format": "openai"
    }
    
    profile_2 = {
        "id": "profile-custom",
        "name": "Custom Profile for Coding Agent",
        "api_key": "custom-coding-key",
        "base_url": "https://api.custom.com/v1",
        "model_name": "claude-3-5-sonnet",
        "api_format": "anthropic"
    }
    
    # Stub get_profile and get_agent_profiles on config_manager
    original_get_profile = config_manager.get_profile
    original_get_agent_profiles = config_manager.get_agent_profiles
    
    config_manager.get_profile = lambda pid: profile_1 if pid == "profile-active" else (profile_2 if pid == "profile-custom" else {})
    config_manager.get_agent_profiles = lambda: {"Coding Agent": "profile-custom"}
    
    try:
        router = ModelRouter()
        
        # Test case 1: Routing general prompt (no agent override)
        resolved_general = router._resolve_profile(profile_1, is_agent=False, task_type="general")
        assert resolved_general["api_key"] == "active-api-key"
        
        # Test case 2: Routing general prompt for Planner Agent (which doesn't have custom mapping)
        resolved_planner = router._resolve_profile(profile_1, is_agent=True, task_type="Planner Agent")
        assert resolved_planner["api_key"] == "active-api-key"
        
        # Test case 3: Routing prompt for Coding Agent (which has custom mapping)
        resolved_coder = router._resolve_profile(profile_1, is_agent=True, task_type="Coding Agent")
        assert resolved_coder["api_key"] == "custom-coding-key"
        assert resolved_coder["model_name"] == "claude-3-5-sonnet"
        assert resolved_coder["base_url"] == "https://api.custom.com/v1"
        
    finally:
        # Restore stubs
        config_manager.get_profile = original_get_profile
        config_manager.get_agent_profiles = original_get_agent_profiles
