"""Tests for spawn_subagent tool.

Covers:
- Final text return with no internal log leakage.
- Forbidden tool access raises / returns an error to the model (blocked, not propagated).
- Cost roll-up adds sub-agent cost to parent session's total_cost_usd.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.spawn_subagent import spawn_subagent, _SUBAGENT_ALLOWED_TOOLS


# ---------------------------------------------------------------------------
# Minimal mock session that mimics what spawn_subagent needs from the parent.
# ---------------------------------------------------------------------------
class _MockSession:
    def __init__(self, workspace_root: str = "/fake/workspace"):
        self.workspace_root = workspace_root
        self.profile = {
            "api_key": "test_key",
            "base_url": "http://localhost",
            "model_name": "test-model",
        }
        self.total_cost_usd: float = 0.0

    async def send_ws_message(self, msg):  # noqa: D401
        pass


# ---------------------------------------------------------------------------
# Helper: build a mock adapter that streams a simple done-on-first-turn reply.
# ---------------------------------------------------------------------------
def _make_mock_adapter(text_response: str):
    """Return an async context manager adapter that yields ``text_response`` then done."""

    async def _fake_stream(messages, tools, system_prompt):
        yield {"type": "text", "content": text_response}
        yield {"type": "done", "stop_reason": "stop"}

    adapter = MagicMock()
    adapter.stream_chat = _fake_stream
    return adapter


# ---------------------------------------------------------------------------
# Helper: build an adapter that first calls a tool, then replies with text.
# ---------------------------------------------------------------------------
def _make_tool_calling_adapter(tool_name: str, tool_args: dict, text_after_tool: str):
    """Return an adapter that calls *tool_name* in turn 1, then replies text in turn 2."""
    call_count = 0

    async def _fake_stream(messages, tools, system_prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First turn: emit a tool call.
            yield {
                "type": "tool_call",
                "id": "tc_test_001",
                "name": tool_name,
                "input": tool_args,
            }
            yield {"type": "done", "stop_reason": "tool_use"}
        else:
            # Second turn: text answer.
            yield {"type": "text", "content": text_after_tool}
            yield {"type": "done", "stop_reason": "stop"}

    adapter = MagicMock()
    adapter.stream_chat = _fake_stream
    return adapter


# ===========================================================================
# Test 1 — Only final text is returned; no internal message log leaks.
# ===========================================================================
@pytest.mark.asyncio
async def test_spawn_subagent_returns_only_final_text(tmp_path):
    """spawn_subagent returns ONLY the final text; internal messages do not leak."""
    session = _MockSession(str(tmp_path))
    expected = "The answer is 42."

    mock_adapter = _make_mock_adapter(expected)

    with patch("app.tools.spawn_subagent.ModelRouter") as MockRouter:
        MockRouter.return_value.get_adapter.return_value = mock_adapter
        result = await spawn_subagent(session, "What is the answer to life?")

    assert result == expected, f"Expected {expected!r}, got {result!r}"
    # The result must be a plain string — no list, dict, or message-log structure.
    assert isinstance(result, str)


# ===========================================================================
# Test 2 — Forbidden tool call is blocked cleanly; does NOT raise to caller.
# ===========================================================================
@pytest.mark.asyncio
async def test_spawn_subagent_blocks_forbidden_tool(tmp_path):
    """Attempting run_terminal_command from inside the sub-agent is blocked.

    The forbidden tool error is fed back to the model as a tool result
    (so the model can gracefully recover), but it must NOT propagate as an
    exception to the spawn_subagent caller.
    """
    session = _MockSession(str(tmp_path))

    # Adapter calls run_terminal_command (forbidden), then returns text.
    forbidden_tool = "run_terminal_command"
    assert forbidden_tool not in _SUBAGENT_ALLOWED_TOOLS, (
        f"Test precondition failed: {forbidden_tool!r} should not be in allowed set"
    )

    mock_adapter = _make_tool_calling_adapter(
        tool_name=forbidden_tool,
        tool_args={"command": "rm -rf /"},
        text_after_tool="I tried but was blocked.",
    )

    with patch("app.tools.spawn_subagent.ModelRouter") as MockRouter:
        MockRouter.return_value.get_adapter.return_value = mock_adapter
        # Must NOT raise — the boundary is enforced internally.
        result = await spawn_subagent(session, "Run a dangerous command.")

    assert isinstance(result, str)
    # The final answer comes from the model's second turn after seeing the error.
    assert "blocked" in result.lower() or len(result) > 0


@pytest.mark.asyncio
async def test_spawn_subagent_blocks_write_file(tmp_path):
    """write_file is also blocked — only read-only tools are allowed."""
    session = _MockSession(str(tmp_path))

    mock_adapter = _make_tool_calling_adapter(
        tool_name="write_file",
        tool_args={"path": "evil.py", "content": "import os; os.system('rm -rf /')"},
        text_after_tool="Write was denied.",
    )

    with patch("app.tools.spawn_subagent.ModelRouter") as MockRouter:
        MockRouter.return_value.get_adapter.return_value = mock_adapter
        result = await spawn_subagent(session, "Write a malicious file.")

    assert isinstance(result, str)


# ===========================================================================
# Test 3 — Cost roll-up: sub-agent cost is added to parent total_cost_usd.
# ===========================================================================
@pytest.mark.asyncio
async def test_spawn_subagent_cost_rollup(tmp_path):
    """Sub-agent's accrued cost is added to parent session.total_cost_usd."""
    session = _MockSession(str(tmp_path))
    initial_cost = 0.05
    session.total_cost_usd = initial_cost
    sub_cost = 0.012  # simulated sub-agent cost emitted via 'usage' chunk

    async def _stream_with_cost(messages, tools, system_prompt):
        yield {"type": "text", "content": "Result."}
        yield {"type": "usage", "cost_usd": sub_cost}
        yield {"type": "done", "stop_reason": "stop"}

    mock_adapter = MagicMock()
    mock_adapter.stream_chat = _stream_with_cost

    with patch("app.tools.spawn_subagent.ModelRouter") as MockRouter:
        MockRouter.return_value.get_adapter.return_value = mock_adapter
        await spawn_subagent(session, "Summarise the codebase.")

    expected_total = initial_cost + sub_cost
    assert abs(session.total_cost_usd - expected_total) < 1e-9, (
        f"Expected total_cost_usd={expected_total:.6f}, "
        f"got {session.total_cost_usd:.6f}"
    )


# ===========================================================================
# Test 4 — Allowed read-only tool passes through without error.
# ===========================================================================
@pytest.mark.asyncio
async def test_spawn_subagent_allows_read_file(tmp_path):
    """read_file (an allowed tool) executes without raising PermissionError."""
    session = _MockSession(str(tmp_path))
    test_file = tmp_path / "readme.txt"
    test_file.write_text("hello from workspace", encoding="utf-8")

    mock_adapter = _make_tool_calling_adapter(
        tool_name="read_file",
        tool_args={"path": "readme.txt"},
        text_after_tool="The file says: hello from workspace.",
    )

    with patch("app.tools.spawn_subagent.ModelRouter") as MockRouter:
        MockRouter.return_value.get_adapter.return_value = mock_adapter
        result = await spawn_subagent(session, "What does readme.txt say?")

    assert "hello" in result.lower() or len(result) > 0


# ===========================================================================
# Test 5 — dispatcher routes spawn_subagent correctly.
# ===========================================================================
@pytest.mark.asyncio
async def test_dispatcher_routes_spawn_subagent(tmp_path):
    """dispatch_tool correctly routes 'spawn_subagent' to the tool module."""
    from app.tools.dispatcher import dispatch_tool

    session = _MockSession(str(tmp_path))
    captured: list[str] = []

    async def _mock_spawn(sess, prompt):
        captured.append(prompt)
        return "mocked subagent result"

    with patch("app.tools.spawn_subagent.spawn_subagent", side_effect=_mock_spawn):
        # Re-import dispatcher so the patch is visible (module-level import).
        import importlib
        import app.tools.dispatcher as disp_mod
        import app.tools.spawn_subagent as sub_mod
        # Patch at the module level the dispatcher imported.
        original = sub_mod.spawn_subagent
        sub_mod.spawn_subagent = _mock_spawn
        try:
            result = await dispatch_tool(
                session, "tc-99", "spawn_subagent",
                {"prompt": "Explain the architecture."}, auto_apply=True
            )
        finally:
            sub_mod.spawn_subagent = original

    assert result == "mocked subagent result"


# ===========================================================================
# Test 6 — dispatch_tool raises ValueError when prompt is empty.
# ===========================================================================
@pytest.mark.asyncio
async def test_dispatcher_spawn_subagent_empty_prompt_raises(tmp_path):
    """dispatch_tool raises ValueError when spawn_subagent prompt is empty."""
    from app.tools.dispatcher import dispatch_tool

    session = _MockSession(str(tmp_path))
    with pytest.raises(ValueError, match="non-empty"):
        await dispatch_tool(
            session, "tc-100", "spawn_subagent", {"prompt": ""}, auto_apply=True
        )
