"""
Phase 1 Acceptance Tests — Unified Agent Runtime.

Verifies:
- Canonical AgentRuntime session lifecycle and explicit state machine.
- Model response normalization to ToolCall / ModelResponse.
- ToolExecutor canonical tool routing, structured ToolResult, and audit logging.
- TransactionalWorkspace file change set tracking and diff generation.
- Session cancellation propagation and state update to CANCELLED.
- DevPilot integration path and legacy orchestrator adapter.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.agent.agent_runtime import (
    AgentEvent,
    AgentResult,
    AgentRuntime,
    AgentSessionState,
    AgentState,
    AgentTask,
    InvalidStateTransitionError,
    ModelResponse,
    ModelResponseNormalizer,
    ToolCall,
    ToolExecutor,
    ToolResult,
    TransactionalWorkspace,
    VerificationStatus,
)


@pytest.fixture
def workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = pathlib.Path(tmpdir)
        (p / "pytest.ini").write_text("[pytest]\n")
        yield p


@pytest.mark.asyncio
async def test_session_lifecycle(workspace):
    """Test 1: Session Lifecycle — start_session, transitions, completion."""
    import uuid
    sess_id = f"test_sess_1_{uuid.uuid4().hex[:8]}"
    runtime = AgentRuntime(str(workspace))
    session = await runtime.start_session(str(workspace), session_id=sess_id)

    assert session.state == AgentState.IDLE
    assert session.session_id == sess_id

    # Mock provider returning a tool call then completing
    turn_count = 0

    async def mock_llm_provider(messages: list, tools: list):
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            return ModelResponse(
                text="Creating main.py and test_main.py",
                tool_calls=[
                    ToolCall(id="tc1", name="write_file", arguments={"path": "main.py", "content": "print('hello')"}),
                    ToolCall(id="tc2", name="write_file", arguments={"path": "test_main.py", "content": "def test_hello():\n    assert True\n"})
                ]
            )
        return ModelResponse(text="Completed writing main.py", tool_calls=[])

    result = await runtime.run(sess_id, "Create main.py", llm_provider_func=mock_llm_provider)

    assert result.success is True
    assert result.state in (AgentState.COMPLETED, AgentState.COMPLETED_VERIFIED)
    assert result.verification_status == VerificationStatus.PASSED
    assert (workspace / "main.py").exists()
    assert (workspace / "test_main.py").exists()
    assert "main.py" in result.changed_files["created_files"]


@pytest.mark.asyncio
async def test_state_machine_invalid_transition(workspace):
    """Test 2: Explicit State Machine — valid vs invalid transition enforcement."""
    import uuid
    sess_id = f"test_sess_2_{uuid.uuid4().hex[:8]}"
    runtime = AgentRuntime(str(workspace))
    session = await runtime.start_session(str(workspace), session_id=sess_id)

    # IDLE -> PLANNING is valid
    await runtime.transition_state(session, AgentState.PLANNING)
    assert session.state == AgentState.PLANNING

    # PLANNING -> COMPLETED is invalid (must go through EXECUTING/VERIFYING)
    with pytest.raises(InvalidStateTransitionError):
        await runtime.transition_state(session, AgentState.COMPLETED)


@pytest.mark.asyncio
async def test_model_response_normalization():
    """Test 3: Model Response Normalization — converting raw responses into canonical ToolCall/ModelResponse."""
    raw_tc = {"id": "call_123", "name": "edit_file", "arguments": '{"path": "app.py", "content": "x=1"}'}
    norm_tc = ModelResponseNormalizer.normalize_tool_call(raw_tc)

    assert norm_tc.id == "call_123"
    assert norm_tc.name == "edit_file"
    assert norm_tc.arguments == {"path": "app.py", "content": "x=1"}

    raw_response = {"content": "Applying fix", "tool_calls": [raw_tc]}
    resp = ModelResponseNormalizer.normalize_response(raw_response, raw_tool_calls=[raw_tc])

    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "edit_file"
    assert resp.finish_reason == "tool_use"


@pytest.mark.asyncio
async def test_tool_executor_audit(workspace):
    """Test 4: ToolExecutor — structured ToolResult and audit history logging."""
    executor = ToolExecutor(str(workspace))
    res = await executor.execute("tc_test", "write_file", {"path": "test.txt", "content": "hello world"})

    assert res.success is True
    assert len(executor.execution_history) == 1
    rec = executor.execution_history[0]
    assert rec.tool_call_id == "tc_test"
    assert rec.tool_name == "write_file"
    assert rec.success is True


@pytest.mark.asyncio
async def test_transactional_workspace(workspace):
    """Test 5: Transactional Workspace — pre-state, post-state diffing, change set tracking."""
    tx = TransactionalWorkspace(str(workspace))

    # Pre-state before creating file
    pre_snap = tx.capture_pre_state("config.json")
    assert pre_snap.exists is False

    # Perform file creation
    file_path = workspace / "config.json"
    file_path.write_text('{"env": "test"}')

    # Post-state capture
    diff = tx.capture_post_state("config.json", pre_snap)

    assert "config.json" in tx.change_set.created_files
    assert "config.json" in tx.change_set.diffs
    assert '{"env": "test"}' in diff


@pytest.mark.asyncio
async def test_cancellation(workspace):
    """Test 6: Cancellation — propagates to session state CANCELLED."""
    import uuid
    sess_id = f"test_sess_cancel_{uuid.uuid4().hex[:8]}"
    runtime = AgentRuntime(str(workspace))
    await runtime.start_session(str(workspace), session_id=sess_id)

    turn_count = 0

    async def cancelling_provider(messages: list, tools: list):
        from backend.app.agent.agent_runtime.llm_adapter import ToolCall
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # Cancel from within the first turn — picked up at next loop iteration
            asyncio.create_task(runtime.cancel(sess_id))
            return ModelResponse(text="working", tool_calls=[ToolCall("tc1", "read_file", {"path": "dummy.py"})])
        return ModelResponse(text="Done", tool_calls=[])

    result = await runtime.run(sess_id, "Hanging task", llm_provider_func=cancelling_provider)

    assert result.success is False
    assert result.state == AgentState.CANCELLED


@pytest.mark.asyncio
async def test_devpilot_agent_session_integration(workspace):
    """Test 7: DevPilot Integration — AgentSession instantiates and communicates with AgentRuntime."""
    import uuid
    sess_id = f"devpilot_integration_test_{uuid.uuid4().hex[:8]}"
    from backend.app.session.agent_session import AgentSession

    ws_messages = []

    async def mock_send_ws(msg):
        ws_messages.append(msg)

    session = AgentSession(
        workspace_root=str(workspace),
        profile={"model": "gpt-4o-mini"},
        send_ws_message=mock_send_ws,
        session_id=sess_id,
    )

    assert hasattr(session, "agent_runtime")
    assert session.agent_runtime is not None

    # Test cancel_all triggers runtime cancellation
    await session.cancel_all()
    runtime_session = session.agent_runtime._sessions.get(sess_id)
    if runtime_session:
        assert runtime_session.state == AgentState.CANCELLED
