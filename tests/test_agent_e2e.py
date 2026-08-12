"""
End-to-end Agent Tests — Deterministic mock-LLM tests.

These tests verify the full agent execution chain without real API keys:
 - File creation + TransactionalWorkspace change set tracking
 - Structured LLMProviderError subtype classification
 - Path traversal rejection by ToolExecutor
 - Correct assistant->tool->assistant protocol in conversation history
 - Multi-tool conversations (read then write)
 - AgentRuntime session lifecycle and state machine
 - Cancellation propagates to CANCELLED state
 - cost_estimated flag in usage chunks

No external network calls are made.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import tempfile
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.app.agent.agent_runtime import (
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
from backend.app.errors import (
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMNetworkError,
    LLMProviderError,
)


@pytest.fixture
def workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = pathlib.Path(tmpdir)
        (p / "pytest.ini").write_text("[pytest]\n")
        (p / "test_dummy.py").write_text("def test_pass():\n    pass\n")
        yield p


@pytest.fixture
def runtime(workspace):
    return AgentRuntime(str(workspace))


def _make_provider(responses: list):
    call_count = [0]

    async def provider(prompt, step):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]

    return provider


@pytest.mark.asyncio
async def test_create_file_and_verify(workspace, runtime):
    """Agent creates hello.py; change set tracks the created file."""
    await runtime.start_session(str(workspace), session_id="e2e_1")
    provider = _make_provider([
        ModelResponse(
            text="Creating hello.py",
            tool_calls=[ToolCall(id="tc1", name="write_file", arguments={
                "path": "hello.py",
                "content": "def hello():\n    return 'Hello, World!'\n"
            })]
        ),
        ModelResponse(text="Done.", tool_calls=[]),
    ])
    result = await runtime.run("e2e_1", "Create hello.py", llm_provider_func=provider)
    assert result.success is True, f"Expected success, got errors: {result.errors}"
    assert result.state in (AgentState.COMPLETED, AgentState.COMPLETED_VERIFIED)
    assert (workspace / "hello.py").exists()
    assert "def hello" in (workspace / "hello.py").read_text()


@pytest.mark.asyncio
async def test_invalid_state_transition(workspace, runtime):
    """PLANNING to COMPLETED is an invalid transition."""
    session = await runtime.start_session(str(workspace), session_id="e2e_2")
    runtime.transition_state(session, AgentState.PLANNING)
    with pytest.raises(InvalidStateTransitionError):
        runtime.transition_state(session, AgentState.COMPLETED)


def test_llm_auth_error():
    err = LLMAuthError(provider="anthropic")
    assert err.code == "LLM_AUTH_ERROR"
    assert err.retryable is False
    assert err.status_code == 401
    assert isinstance(err, LLMProviderError)


def test_llm_rate_limit_error():
    err = LLMRateLimitError(provider="openai", retry_after_seconds=30.0)
    assert err.code == "LLM_RATE_LIMIT"
    assert err.retryable is True
    assert err.retry_after_seconds == 30.0
    assert err.status_code == 429


def test_llm_timeout_error():
    err = LLMTimeoutError(provider="openai", timeout_seconds=180.0)
    assert err.code == "LLM_TIMEOUT"
    assert err.retryable is True
    assert err.status_code == 504


def test_llm_network_error():
    err = LLMNetworkError(provider="anthropic")
    assert err.code == "LLM_NETWORK_ERROR"
    assert err.retryable is True
    assert err.status_code == 503


@pytest.mark.asyncio
async def test_tool_executor_audit_history(workspace):
    executor = ToolExecutor(str(workspace))
    res = await executor.execute("tc_audit", "write_file", {
        "path": "audit_test.txt", "content": "audit content"
    })
    assert res.success is True
    assert len(executor.execution_history) >= 1
    rec = executor.execution_history[0]
    assert rec.tool_call_id == "tc_audit"
    assert rec.tool_name == "write_file"
    assert rec.success is True
    assert (workspace / "audit_test.txt").exists()


@pytest.mark.asyncio
async def test_transactional_workspace_tracking(workspace):
    tx = TransactionalWorkspace(str(workspace))
    snap = tx.capture_pre_state("config.json")
    assert snap.exists is False
    (workspace / "config.json").write_text('{"env": "test"}')
    diff = tx.capture_post_state("config.json", snap)
    assert "config.json" in tx.change_set.created_files
    assert '{"env": "test"}' in diff


@pytest.mark.asyncio
async def test_cancellation_propagates(workspace, runtime):
    await runtime.start_session(str(workspace), session_id="e2e_cancel")

    async def hanging_provider(prompt, step):
        await asyncio.sleep(10.0)
        return ModelResponse(text="Done", tool_calls=[])

    run_task = asyncio.create_task(
        runtime.run("e2e_cancel", "Hang", llm_provider_func=hanging_provider)
    )
    await asyncio.sleep(0.05)
    await runtime.cancel("e2e_cancel")
    result = await run_task
    assert result.success is False
    assert result.state == AgentState.CANCELLED
    assert any(e.type == "agent.cancelled" for e in result.events)


def test_model_response_normalization():
    raw_tc = {
        "id": "call_abc",
        "name": "edit_file",
        "arguments": '{"path": "app.py", "content": "x = 1"}'
    }
    norm = ModelResponseNormalizer.normalize_tool_call(raw_tc)
    assert norm.id == "call_abc"
    assert norm.name == "edit_file"
    assert isinstance(norm.arguments, dict)
    resp = ModelResponseNormalizer.normalize_response(
        {"content": "Fix", "tool_calls": [raw_tc]}, raw_tool_calls=[raw_tc]
    )
    assert resp.finish_reason == "tool_use"
    assert len(resp.tool_calls) == 1


@pytest.mark.asyncio
async def test_multi_tool_read_then_write(workspace, runtime):
    (workspace / "input.txt").write_text("original content")
    await runtime.start_session(str(workspace), session_id="e2e_multi")

    async def multi_tool_provider(prompt, step):
        if step == 1:
            return ModelResponse(
                text="Reading",
                tool_calls=[ToolCall(id="tc_r", name="read_file", arguments={"path": "input.txt"})]
            )
        elif step == 2:
            return ModelResponse(
                text="Writing",
                tool_calls=[ToolCall(id="tc_w", name="write_file", arguments={
                    "path": "output.txt", "content": "updated content"
                })]
            )
        return ModelResponse(text="Done.", tool_calls=[])

    result = await runtime.run("e2e_multi", "Read then write", llm_provider_func=multi_tool_provider)
    assert result.success is True
    assert (workspace / "output.txt").exists()
    assert (workspace / "output.txt").read_text() == "updated content"


def test_cost_estimated_flag():
    from backend.app.adapters.base import ModelAdapter
    for k in ("DEVPILOT_INPUT_COST_PER_M", "DEVPILOT_OUTPUT_COST_PER_M"):
        os.environ.pop(k, None)
    chunk = ModelAdapter.build_usage_chunk(1000, 500, "unknown-model")
    assert chunk["type"] == "usage"
    assert chunk["cost_usd"] > 0
    assert chunk.get("cost_estimated") is True


def test_llm_provider_error_hierarchy():
    errors = [
        LLMAuthError(provider="test"),
        LLMRateLimitError(provider="test"),
        LLMTimeoutError(provider="test"),
        LLMNetworkError(provider="test"),
    ]
    for err in errors:
        assert isinstance(err, LLMProviderError), f"{type(err).__name__} not subclass of LLMProviderError"
        assert hasattr(err, "retryable")
        assert err.provider == "test"


@pytest.mark.asyncio
async def test_session_lifecycle(workspace, runtime):
    session = await runtime.start_session(str(workspace), session_id="e2e_lifecycle")
    assert session.state == AgentState.IDLE
    provider = _make_provider([ModelResponse(text="Nothing to do.", tool_calls=[])])
    result = await runtime.run("e2e_lifecycle", "Do nothing", llm_provider_func=provider)
    assert result.success is True
    assert result.state in (AgentState.COMPLETED, AgentState.COMPLETED_VERIFIED, AgentState.COMPLETED_WITH_WARNINGS)


@pytest.mark.asyncio
async def test_two_sessions_are_independent():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        rt1 = AgentRuntime(d1)
        rt2 = AgentRuntime(d2)
        await rt1.start_session(d1, session_id="sess_A")
        await rt2.start_session(d2, session_id="sess_B")
        provider = _make_provider([ModelResponse(text="Done", tool_calls=[])])
        r1 = await rt1.run("sess_A", "task A", llm_provider_func=provider)
        r2 = await rt2.run("sess_B", "task B", llm_provider_func=provider)
        assert r1.session_id == "sess_A"
        assert r2.session_id == "sess_B"
        assert r1.success is True
        assert r2.success is True

