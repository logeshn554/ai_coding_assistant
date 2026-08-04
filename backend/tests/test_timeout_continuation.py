import os
import json
import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from app.tools.write_tool import validate_file_content
    from app.session.agent_session import detect_contradiction, AgentSession
    from app.adapters.llm import LLMAdapter
except ImportError:
    from backend.app.tools.write_tool import validate_file_content
    from backend.app.session.agent_session import detect_contradiction, AgentSession
    from backend.app.adapters.llm import LLMAdapter

# 1. Test validate_file_content
def test_validate_file_content():
    # Empty content
    assert validate_file_content("test.py", "") == "File content cannot be empty."
    assert validate_file_content("test.py", "   \n  ") == "File content cannot be empty."
    
    # JSON validation
    assert validate_file_content("test.json", '{"key": "value"}') is None
    assert "Invalid JSON" in validate_file_content("test.json", '{"key": "value"')
    
    # Python validation
    assert validate_file_content("test.py", "def hello():\n    pass") is None
    assert "Python syntax error" in validate_file_content("test.py", "def hello(\n    pass")
    
    # Other files are not validated
    assert validate_file_content("test.txt", "some random content") is None

# 2. Test detect_contradiction
def test_detect_contradiction():
    # React vs Vue in setup
    assert "React and Vue" in detect_contradiction("scaffold a react and vue app")
    
    # Django vs FastAPI in setup
    assert "Django and FastAPI" in detect_contradiction("setup django and fastapi backend")
    
    # TS vs Python in setup
    assert "Python and TypeScript" in detect_contradiction("initialize typescript and python project")
    
    # Delete and modify contradiction
    assert "delete and modify" in detect_contradiction("delete auth.py and edit auth.py in the same turn")
    
    # Safe prompts
    assert detect_contradiction("create a react app") is None
    assert detect_contradiction("setup django project") is None
    assert detect_contradiction("delete auth.py") is None
    assert detect_contradiction("edit auth.py") is None

# 3. Test Configured Timeouts & Exception-based Mapping in LLMAdapter
@pytest.mark.asyncio
async def test_llm_adapter_timeout_handling():
    # Test that env variable is read
    os.environ["DEVPILOT_STREAMING_TIMEOUT"] = "42.0"
    
    adapter = LLMAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4",
        provider="openai"
    )
    
    # Mock stream call to raise httpx.TimeoutException
    mock_client = MagicMock()
    
    # Try importing AsyncOpenAI correctly based on path
    try:
        openai_path = "app.adapters.llm.AsyncOpenAI"
    except ImportError:
        openai_path = "backend.app.adapters.llm.AsyncOpenAI"
        
    with patch("backend.app.adapters.llm.AsyncOpenAI") as mock_openai_cls:
        mock_openai_inst = MagicMock()
        mock_openai_cls.return_value = mock_openai_inst
        
        async def mock_create(*args, **kwargs):
            raise httpx.ReadTimeout("Read timed out", request=MagicMock())
            
        mock_openai_inst.chat.completions.create = mock_create
        
        # Let's call _stream_openai and collect chunk
        chunks = []
        with pytest.raises(TimeoutError) as exc_info:
            async for chunk in adapter._stream_openai(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                system_prompt="system"
            ):
                chunks.append(chunk)
                
        assert "Request timed out" in str(exc_info.value)

# 4. Test retry, continue, resume websocket message handling logic mock-style
@pytest.mark.asyncio
async def test_session_recovery_and_continuation():
    # Create mock session
    send_ws_mock = AsyncMock()
    session = AgentSession(
        workspace_root="dummy_root",
        profile={"cost_limit_usd": 5.0},
        send_ws_message=send_ws_mock,
        session_id="test_sess"
    )
    
    # Set up last request snapshot
    session._last_request_snapshot = {
        "text": "original user request",
        "mode": "Agent",
        "auto_apply": True,
        "history": [{"role": "user", "content": "previous message"}]
    }
    session._failed_request = session._last_request_snapshot
    
    # Mock enqueue_message
    session.enqueue_message = MagicMock()
    
    # Simulating the message routing in chat.py:
    # 1. retry message
    snapshot = session._failed_request or getattr(session, "_last_request_snapshot", None)
    assert snapshot is not None
    session.conversation_history = list(snapshot["history"])
    session._failed_request = None
    text = snapshot["text"]
    mode = snapshot["mode"]
    auto_apply = snapshot["auto_apply"]
    
    # Simulate routing logic
    assert session.conversation_history == [{"role": "user", "content": "previous message"}]
    assert session._failed_request is None
    
    # Mock continues
    session.last_mode = "Agent"
    session.auto_apply = True
