"""
End-to-end integration tests for the canonical AgentWorker → AgentRuntime → ToolExecutor path.

Uses a deterministic mock LLM to exercise the real production wiring without
making actual network requests to LLM providers.

Covers:
  Test A: Create hello.py → COMPLETED_VERIFIED
  Test B: Multiple tool calls → multiple files created
  Test C: Tool fails once → agent recovers
  Test D: Verification fails → LLM repairs → rerun
  Test E: Missing LLM provider → FAILED (never COMPLETED)
  Test F: Outside-workspace file access → denied
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.agent.agent_runtime.llm_adapter import ModelResponse, ToolCall
from backend.app.agent.agent_runtime.runtime import (
    AgentRuntime,
    AgentState,
    AgentTask,
    VerificationStatus,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

class _MockLLMSequence:
    """
    Deterministic mock LLM. Returns ModelResponse objects in order.
    Once the sequence is exhausted it returns an empty text response.
    """

    def __init__(self, responses: List[ModelResponse]):
        self._responses = list(responses)
        self._idx = 0

    async def __call__(self, messages: list, tools: list) -> ModelResponse:
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return ModelResponse(text="Task complete.", tool_calls=[], finish_reason="end_turn")


def _tool_call(name: str, args: dict, tc_id: str | None = None) -> ToolCall:
    return ToolCall(id=tc_id or f"tc_{uuid.uuid4().hex[:8]}", name=name, arguments=args)


def _resp(text: str | None = None, calls: List[ToolCall] | None = None) -> ModelResponse:
    return ModelResponse(text=text, tool_calls=calls or [], finish_reason="tool_use" if calls else "end_turn")


async def _run_runtime(
    workspace_root: str,
    task_description: str,
    llm_sequence,
    max_turns: int = 20,
    patch_verification: bool = True,
):
    """Convenience wrapper: initialises a fresh AgentRuntime and runs it."""
    runtime = AgentRuntime(workspace_root)
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    await runtime.start_session(workspace_root, session_id=session_id)

    task = AgentTask(id=session_id, description=task_description, mode="Agent", auto_apply=True)

    if patch_verification:
        with patch(
            "backend.app.agent.autonomous.verification_engine.VerificationEngine.run_phase_command",
            new_callable=AsyncMock,
        ) as mock_verify:
            from backend.app.agent.autonomous.verification_engine import VerificationResult
            mock_verify.return_value = VerificationResult(
                success=True, command="mock-check", output="OK", duration_seconds=0.1
            )
            result = await runtime.run(
                session_id=session_id,
                task=task,
                mode="Agent",
                auto_apply=True,
                llm_provider_func=llm_sequence,
                max_turns=max_turns,
            )
    else:
        result = await runtime.run(
            session_id=session_id,
            task=task,
            mode="Agent",
            auto_apply=True,
            llm_provider_func=llm_sequence,
            max_turns=max_turns,
        )

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Test A — Create hello.py
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_create_hello_py():
    """
    Mock LLM issues a write_file tool call to create hello.py.
    Expected: file exists, state is not FAILED.
    """
    with tempfile.TemporaryDirectory() as workspace:
        hello_path = os.path.join(workspace, "hello.py")
        content = 'print("hello")\n'

        llm = _MockLLMSequence([
            _resp(calls=[_tool_call("write_file", {"path": hello_path, "content": content})]),
            _resp(text="hello.py created successfully."),
        ])

        result = await _run_runtime(workspace, "Create hello.py that prints hello", llm)

        assert os.path.isfile(hello_path), "hello.py was not created"
        assert 'print("hello")' in open(hello_path).read()
        assert result.state not in (AgentState.FAILED, AgentState.CANCELLED), \
            f"Unexpected state: {result.state} errors: {result.errors}"


# ──────────────────────────────────────────────────────────────────────────────
# Test B — Multiple tool calls, multiple files
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b_multiple_tool_calls():
    """
    Mock LLM issues two sequential write_file calls.
    Expected: both files exist.
    """
    with tempfile.TemporaryDirectory() as workspace:
        app_path = os.path.join(workspace, "app.py")
        req_path = os.path.join(workspace, "requirements.txt")

        llm = _MockLLMSequence([
            _resp(calls=[
                _tool_call("write_file", {"path": app_path, "content": "# app\n"}),
                _tool_call("write_file", {"path": req_path, "content": "flask\n"}),
            ]),
            _resp(text="Done."),
        ])

        result = await _run_runtime(workspace, "Create app.py and requirements.txt", llm)

        assert os.path.isfile(app_path), "app.py not created"
        assert os.path.isfile(req_path), "requirements.txt not created"
        assert result.state != AgentState.FAILED, f"state: {result.state}"


# ──────────────────────────────────────────────────────────────────────────────
# Test C — Tool fails once, agent retries
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_c_tool_fails_once_agent_recovers():
    """
    First tool call uses a forbidden path, second uses a valid path.
    Expected: valid file exists, agent did not crash.
    """
    with tempfile.TemporaryDirectory() as workspace:
        valid_path = os.path.join(workspace, "recovered.py")

        llm = _MockLLMSequence([
            _resp(calls=[
                _tool_call("write_file", {"path": "/etc/bad_path.py", "content": "evil"}),
            ]),
            _resp(calls=[
                _tool_call("write_file", {"path": valid_path, "content": "# recovered\n"}),
            ]),
            _resp(text="Recovered successfully."),
        ])

        result = await _run_runtime(workspace, "Write a file", llm)

        assert os.path.isfile(valid_path), "Valid file not created after recovery"
        assert result.state != AgentState.CANCELLED


# ──────────────────────────────────────────────────────────────────────────────
# Test D — Verification fails → LLM repair → rerun
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_d_verification_fails_llm_repairs():
    """
    Verification fails once; LLM is invoked with the failure context and produces
    a repair tool call. Verification passes on second attempt.
    """
    with tempfile.TemporaryDirectory() as workspace:
        file_path = os.path.join(workspace, "fixed.py")
        repair_path = os.path.join(workspace, "fixed.py")

        from backend.app.agent.autonomous.verification_engine import VerificationResult

        verify_call_count = {"n": 0}

        async def patched_verify(cmd):
            verify_call_count["n"] += 1
            if verify_call_count["n"] == 1:
                return VerificationResult(success=False, command="mock-check", output="SyntaxError: bad code", duration_seconds=0.1)
            return VerificationResult(success=True, command="mock-check", output="OK", duration_seconds=0.1)

        repair_tool_call = _tool_call("write_file", {"path": repair_path, "content": "# fixed\n"})

        llm = _MockLLMSequence([
            _resp(calls=[_tool_call("write_file", {"path": file_path, "content": "bad code\n"})]),
            _resp(text="Implementation done."),
            _resp(calls=[repair_tool_call]),
            _resp(text="Fixed."),
        ])

        runtime = AgentRuntime(workspace)
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        await runtime.start_session(workspace, session_id=session_id)
        task = AgentTask(id=session_id, description="Fix the code", mode="Agent", auto_apply=True)

        with patch(
            "backend.app.agent.autonomous.verification_engine.VerificationEngine.run_phase_command",
            side_effect=patched_verify,
        ):
            result = await runtime.run(
                session_id=session_id,
                task=task,
                mode="Agent",
                auto_apply=True,
                llm_provider_func=llm,
            )

        assert verify_call_count["n"] >= 2, f"Expected >=2 verify calls, got {verify_call_count['n']}"
        assert os.path.isfile(repair_path), "Repair file not created"


# ──────────────────────────────────────────────────────────────────────────────
# Test E — Missing LLM provider → explicit FAILED, never COMPLETED
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e_missing_llm_provider_fails_explicitly():
    """
    Passing llm_provider_func=None must result in state=FAILED, never COMPLETED.
    """
    with tempfile.TemporaryDirectory() as workspace:
        runtime = AgentRuntime(workspace)
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        await runtime.start_session(workspace, session_id=session_id)
        task = AgentTask(id=session_id, description="Do something", mode="Agent", auto_apply=True)

        with patch(
            "backend.app.agent.autonomous.verification_engine.VerificationEngine.run_phase_command",
            new_callable=AsyncMock,
        ):
            result = await runtime.run(
                session_id=session_id,
                task=task,
                mode="Agent",
                llm_provider_func=None,
            )

        assert result.state == AgentState.FAILED, \
            f"Expected FAILED, got {result.state}"
        assert result.state not in (
            AgentState.COMPLETED,
            AgentState.COMPLETED_VERIFIED,
            AgentState.COMPLETED_WITH_WARNINGS,
        ), "Must never report success when no LLM was called"
        assert result.errors, "Expected at least one error message"
        assert any(
            "provider" in e.lower() or "llm" in e.lower() or "runtime" in e.lower()
            for e in result.errors
        ), f"Error messages didn't mention LLM/provider: {result.errors}"


# ──────────────────────────────────────────────────────────────────────────────
# Test F — Outside-workspace access is denied
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_f_outside_workspace_access_denied():
    """
    LLM tool call attempts to write a file outside the workspace directory.
    Expected: permission denied, file not created at forbidden path.
    """
    with tempfile.TemporaryDirectory() as workspace:
        with tempfile.TemporaryDirectory() as outside_dir:
            forbidden_path = os.path.join(outside_dir, "evil_devpilot_test.py")

            llm = _MockLLMSequence([
                _resp(calls=[_tool_call("write_file", {"path": forbidden_path, "content": "evil"})]),
                _resp(text="Done."),
            ])

            result = await _run_runtime(workspace, "Write outside workspace", llm)

            assert not os.path.isfile(forbidden_path), \
                "File was created outside workspace — path traversal protection failed!"


# ──────────────────────────────────────────────────────────────────────────────
# Regression: no fake success without LLM
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_llm_provider_raises_runtime_error():
    """
    The runtime.run() loop must result in FAILED (not silently succeed)
    when llm_provider_func is not provided.
    """
    with tempfile.TemporaryDirectory() as workspace:
        runtime = AgentRuntime(workspace)
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        await runtime.start_session(workspace, session_id=session_id)
        task = AgentTask(id=session_id, description="Test", mode="Agent", auto_apply=True)

        with patch(
            "backend.app.agent.autonomous.verification_engine.VerificationEngine.run_phase_command",
            new_callable=AsyncMock,
        ):
            result = await runtime.run(
                session_id=session_id,
                task=task,
                mode="Agent",
                llm_provider_func=None,
            )

        assert result.state == AgentState.FAILED
        assert not result.success


# ──────────────────────────────────────────────────────────────────────────────
# Regression: Worker resolves workspace root, not DATABASE_URL
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_worker_resolves_workspace_root_not_db_url():
    """
    AgentWorker._resolve_workspace_root must return the workspace root_identifier,
    never settings.DATABASE_URL.
    """
    from backend.app.infrastructure.worker import AgentWorker

    with tempfile.TemporaryDirectory() as workspace:
        worker = AgentWorker("test-worker")

        mock_run = MagicMock()
        mock_run.workspace_root = workspace
        mock_run.workspace = MagicMock()
        mock_run.workspace.root_identifier = workspace
        mock_run.id = "test-run-id"

        resolved = await worker._resolve_workspace_root(mock_run)

        assert resolved == workspace, f"Expected {workspace!r}, got {resolved!r}"
        assert "://" not in resolved, f"Workspace root contains URL scheme: {resolved}"
        assert not resolved.startswith("sqlite"), "Workspace root must not be a SQLite URL"
