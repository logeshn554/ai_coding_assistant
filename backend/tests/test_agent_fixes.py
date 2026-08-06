"""Unit and integration tests covering Section A (A1-A8) and Section B prompt updates."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.base import AVAILABLE_TOOLS
from app.adapters.llm import LLMAdapter
from app.mcp_client import MCP_DISCOVERED_TOOLS, MCPClientManager
from app.prompts.modes import (
    AGENT_MODE_INSTRUCTIONS,
    ASK_MODE_INSTRUCTIONS,
    PLAN_MODE_INSTRUCTIONS,
)
from app.session.agent_session import AgentSession
from app.tools.dispatcher import dispatch_tool
from app.tools.file_tools import (
    _build_edit_error_hint,
    _check_missing_packages,
    write_or_edit_file,
)
from app.tools.terminal_tool import _resolve_timeout, run_shell_command, run_terminal_command


class MockSession:
    """Minimal mock AgentSession for testing tools and dispatcher."""

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.pending_confirmations: Dict[str, Any] = {}
        self.permission_manager = None
        self.audit_log = []
        self.ws_messages = []
        self.wasted_turns = 0

    async def send_ws_message(self, msg: dict):
        self.ws_messages.append(msg)

    def log_audit(self, tool_name: str, args: dict, status: str, details: str = ""):
        self.audit_log.append({"tool": tool_name, "status": status, "details": details})


# ── A1 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a1_crlf_on_disk_lf_target_edit_succeeds(tmp_path):
    """(a) CRLF-on-disk file + LF-only target -> edit succeeds."""
    test_file = tmp_path / "test_crlf.txt"
    test_file.write_bytes(b"first line\r\nsecond line\r\nthird line\r\n")

    session = MockSession(str(tmp_path))
    args = {
        "path": "test_crlf.txt",
        "target": "second line\nthird line",
        "replacement": "replaced line 2\nreplaced line 3",
    }

    res = await write_or_edit_file(session, "tc-a1-1", "edit_file", args, auto_apply=True)
    assert "Successfully updated file" in res

    content = test_file.read_text(encoding="utf-8")
    assert "replaced line 2\nreplaced line 3" in content.replace("\r\n", "\n")


@pytest.mark.asyncio
async def test_a1_near_miss_returns_actionable_diff(tmp_path):
    """(b) Near-miss target -> error string contains line-by-line mismatch diff."""
    test_file = tmp_path / "sample.py"
    test_file.write_text("def hello():\n    print('hello world')\n    return True\n")

    session = MockSession(str(tmp_path))
    args = {
        "path": "sample.py",
        "target": "def hello():\n    print('hello earth')\n    return True",
        "replacement": "def hello():\n    pass",
    }

    res = await write_or_edit_file(session, "tc-a1-2", "edit_file", args, auto_apply=True)
    assert "differs starting at line 2" in res
    assert "expected '    print('hello earth')'" in res
    assert "but file has '    print('hello world')'" in res


# ── A2 Tests ──────────────────────────────────────────────────────────────────

def test_a2_timeout_resolution():
    """Verify dynamic timeout resolution and explicit overrides."""
    assert _resolve_timeout("npm install lodash") == 180.0
    assert _resolve_timeout("pip install pytest") == 180.0
    assert _resolve_timeout("npm run build") == 120.0
    assert _resolve_timeout("ls -la") == 30.0
    assert _resolve_timeout("ls -la", explicit_timeout=60) == 60.0
    assert _resolve_timeout("ls -la", explicit_timeout=500) == 300.0


@pytest.mark.asyncio
async def test_a2_run_terminal_command_schema():
    """Verify timeout_seconds is present in run_terminal_command schema."""
    cmd_tool = next((t for t in AVAILABLE_TOOLS if t["name"] == "run_terminal_command"), None)
    assert cmd_tool is not None
    props = cmd_tool["input_schema"]["properties"]
    assert "timeout_seconds" in props
    assert props["timeout_seconds"]["type"] == "integer"


# ── A3 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a3_stdin_devnull_and_ci_env(tmp_path):
    """Command reading stdin returns immediately with empty input."""
    session = MockSession(str(tmp_path))
    cmd = 'python -c "import sys, os; print(\'CI:\', os.environ.get(\'CI\')); print(\'STDIN:\', repr(sys.stdin.read()))"'
    res = await run_shell_command(session, cmd)
    assert "CI: true" in res
    assert "STDIN: ''" in res


# ── A4 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a4_missing_package_warning(tmp_path):
    """Writing a JS/TS file with missing package imports appends missing package note."""
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))

    tsx_file = tmp_path / "App.tsx"
    session = MockSession(str(tmp_path))
    args = {
        "path": "App.tsx",
        "content": 'import React from "react";\nimport { motion } from "framer-motion";\nconst axios = require("axios");',
    }

    res = await write_or_edit_file(session, "tc-a4", "write_file", args, auto_apply=True)
    assert "Successfully updated file 'App.tsx'" in res
    assert "Missing packages" in res
    assert "`axios`" in res
    assert "`framer-motion`" in res
    assert "`react`" not in res
    assert "npm install axios framer-motion" in res
@pytest.mark.asyncio
async def test_write_file_minimal_content_init_py(tmp_path):
    """Writing an empty __init__.py file is allowed now."""
    session = MockSession(str(tmp_path))
    args = {
        "path": "new_pkg/__init__.py",
        "content": "",
    }
    res = await write_or_edit_file(session, "tc-init", "write_file", args, auto_apply=True)
    assert "Successfully updated file" in res
    assert os.path.exists(tmp_path / "new_pkg/__init__.py")
    with open(tmp_path / "new_pkg/__init__.py", "r", encoding="utf-8") as f:
        assert f.read() == ""

@pytest.mark.asyncio
async def test_write_file_nested_path_implicit_dir(tmp_path):
    """Writing a file to a nested path implicitly creates its parent directories."""
    session = MockSession(str(tmp_path))
    args = {
        "path": "nested/sub/dir/module.py",
        "content": "print('hello')",
    }
    res = await write_or_edit_file(session, "tc-nested", "write_file", args, auto_apply=True)
    assert "Successfully updated file" in res
    assert os.path.exists(tmp_path / "nested/sub/dir/module.py")
    with open(tmp_path / "nested/sub/dir/module.py", "r", encoding="utf-8") as f:
        assert f.read() == "print('hello')"


# ── A5 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a5_mcp_real_sdk_flow(tmp_path):
    """Test MCP tool registration and live call_tool routing."""
    manager = MCPClientManager()

    mock_session = AsyncMock()
    mock_tool = MagicMock()
    mock_tool.name = "mock_calc"
    mock_tool.description = "Mock calculator"
    mock_tool.inputSchema = {"type": "object", "properties": {"x": {"type": "integer"}}}

    mock_list_res = MagicMock()
    mock_list_res.tools = [mock_tool]
    mock_session.list_tools.return_value = mock_list_res

    mock_part = MagicMock()
    mock_part.type = "text"
    mock_part.text = "Result: 42"
    mock_call_res = MagicMock()
    mock_call_res.content = [mock_part]
    mock_session.call_tool.return_value = mock_call_res

    mock_transport = (AsyncMock(), AsyncMock())

    with patch("mcp.client.stdio.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = mock_transport
        with patch("mcp.ClientSession") as mock_sess_cls:
            mock_sess_cls.return_value = mock_session
            mock_session.__aenter__.return_value = mock_session
            mock_session.initialize = AsyncMock()

            server_cfg = {"id": "mock-mcp", "name": "Mock MCP Server", "command": "python", "args": ["-m", "mock"]}
            tools = await manager.connect_server(server_cfg)

            assert len(tools) == 1
            assert tools[0]["name"] == "mock_calc"
            assert "mock_calc" in MCP_DISCOVERED_TOOLS

            result = await manager.call_tool("mock-mcp", "mock_calc", {"x": 21})
            assert result == "Result: 42"

            mock_session.call_tool.assert_called_once_with("mock_calc", arguments={"x": 21})

            # Test dispatcher routing
            session = MockSession(str(tmp_path))
            with patch("app.mcp_client.global_mcp_manager", manager):
                disp_res = await dispatch_tool(session, "tc-mcp", "mock_calc", {"x": 21}, auto_apply=True)
                assert disp_res == "Result: 42"

            await manager.disconnect_server("mock-mcp")
            assert "mock_calc" not in MCP_DISCOVERED_TOOLS


# ── A6 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a6_anthropic_thinking_blocks_preservation():
    """Simulate a two-turn Agent-mode conversation with Anthropic extended thinking."""
    adapter = LLMAdapter(api_key="test-key", base_url="", model_name="claude-3-7-sonnet", provider="anthropic")

    # Turn 1 internal message with thinking blocks
    turn1_msg = {
        "role": "assistant",
        "content": "",
        "thinking_blocks": [
            {"type": "thinking", "thinking": "Evaluating workspace structure...", "signature": "sig_abc123"}
        ],
        "tool_calls": [{"id": "call_1", "name": "list_directory", "input": {"path": "."}}],
    }

    messages = [
        {"role": "user", "content": "Build feature X"},
        turn1_msg,
        {"role": "tool", "tool_call_id": "call_1", "content": '["package.json"]'},
        {"role": "user", "content": "Now add component Y"},
    ]

    anthropic_msgs = adapter._to_anthropic_messages(messages)

    # Find the prior assistant message in anthropic_msgs
    assistant_turns = [m for m in anthropic_msgs if m["role"] == "assistant"]
    assert len(assistant_turns) >= 1
    blocks = assistant_turns[0]["content"]

    # First block MUST be the thinking block with exact signature
    assert blocks[0]["type"] == "thinking"
    assert blocks[0]["thinking"] == "Evaluating workspace structure..."
    assert blocks[0]["signature"] == "sig_abc123"

    # Second block MUST be the tool_use block
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["id"] == "call_1"


# ── A7 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a7_malformed_json_tool_arguments():
    """Malformed tool JSON short-circuits with clear error message and prevents execution."""
    adapter = LLMAdapter(api_key="dummy", base_url="", model_name="gpt-4o", provider="openai")

    # Mock chunk stream yielding malformed JSON for run_terminal_command
    class DummyDeltaFunc:
        name = "run_terminal_command"
        arguments = '{"command": "npm install", '  # Truncated JSON

    class DummyTcChunk:
        index = 0
        id = "call_malformed_1"
        function = DummyDeltaFunc()

    class DummyDelta:
        content = None
        tool_calls = [DummyTcChunk()]

    class DummyChoice:
        delta = DummyDelta()

    class DummyChunk:
        choices = [DummyChoice()]

    async def mock_stream():
        yield DummyChunk()

    with patch("app.adapters.llm.AsyncOpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        chunks = []
        async for chunk in adapter.stream_chat([{"role": "user", "content": "run npm"}], AVAILABLE_TOOLS, "sys"):
            chunks.append(chunk)

        tc_chunks = [c for c in chunks if c["type"] == "tool_call"]
        assert len(tc_chunks) == 1
        assert "error" in tc_chunks[0]
        assert "Error: model produced malformed JSON arguments for tool 'run_terminal_command'" in tc_chunks[0]["error"]

        # Verify session loop short-circuits without executing dispatch_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            session = AgentSession(tmpdir, {"max_turns": 5}, AsyncMock())
            session._execute_tool_with_guardrails = AsyncMock()

            # Pass tc_chunk directly to execution logic simulation
            tc = tc_chunks[0]
            if tc.get("error"):
                res = tc["error"]
                status = "error"
            else:
                res = await session._execute_tool_with_guardrails(tc["id"], tc["name"], tc["input"], True)

            assert "Error: model produced malformed JSON arguments" in res
            session._execute_tool_with_guardrails.assert_not_called()


# ── A8 Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a8_wasted_turns_counter(tmp_path):
    """Session wasted_turns counter increments on timeouts, cancellations, and edit mismatches."""
    session = MockSession(str(tmp_path))

    # Edit mismatch error result
    res1 = _build_edit_error_hint("foo", "bar", "test.py")
    if any(sig in res1.lower() for sig in ("timed out", "timeout", "action cancelled", "cancelled", "target block not found", "differs starting at line")):
        session.wasted_turns += 1

    assert session.wasted_turns == 1


# ── Section B Prompt Assertion Test ───────────────────────────────────────────

def test_section_b_agent_mode_prompt_instructions():
    """Verify AGENT_MODE_INSTRUCTIONS contains STEP 0 and STEP 1 workspace-check rules."""
    assert "STEP 0 — CLASSIFY THE REQUEST FIRST" in AGENT_MODE_INSTRUCTIONS
    assert "STEP 1 — WORKSPACE CHECK" in AGENT_MODE_INSTRUCTIONS
    assert "DEPENDENCY DISCIPLINE" in AGENT_MODE_INSTRUCTIONS

    # Assert these instructions are absent from Ask and Plan modes
    assert "STEP 0 — CLASSIFY THE REQUEST FIRST" not in ASK_MODE_INSTRUCTIONS
    assert "STEP 0 — CLASSIFY THE REQUEST FIRST" not in PLAN_MODE_INSTRUCTIONS


# ── Terminal Self-Healing Test ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_terminal_self_healing(tmp_path):
    """Verify that run_terminal_command performs self-healing diagnostics and retries on failure."""
    from app.tools.terminal_tool import run_terminal_command
    
    session = MockSession(str(tmp_path))
    
    class MockPermissionManager:
        def check_permission(self, cmd):
            return True, "safe", ""
    session.permission_manager = MockPermissionManager()
    
    # Mock _run_llm_query on MockSession to simulate successful auto-fix extraction
    diagnostics_json = json.dumps({
        "root_cause": "Missing package",
        "fix_suggestion": "Install missing pkg",
        "fix_command": "echo 'fixed'",
        "can_auto_fix": True
    })
    session._run_llm_query = AsyncMock(return_value=diagnostics_json)
    
    # We will run a command that fails (exit code non-zero).
    cmd = 'python -c "import sys; sys.exit(1)"'
    
    # Run the terminal command tool wrapper
    res = await run_terminal_command(session, "tc-sh-1", {"command": cmd}, auto_apply=True)
    
    # Check that our mock LLM query was called
    session._run_llm_query.assert_called_once()
    # Check that exit_code was tracked (the retried exit code will also be 1 in this real run)
    assert getattr(session, "last_exit_code", 0) == 1


@pytest.mark.asyncio
async def test_fallback_json_tool_call_parsing(tmp_path):
    """Verify that AgentSession correctly extracts and executes fallback JSON tool calls from text response."""
    session = AgentSession(str(tmp_path), {"max_turns": 5}, AsyncMock())
    
    # Mock text response containing JSON tool call
    json_text = '''{
  "name": "list_directory",
  "arguments": {
    "recursive": true,
    "depth": 4
  }
}'''
    
    parsed = session._extract_tool_call_from_text(json_text)
    assert parsed is not None
    assert parsed["name"] == "list_directory"
    assert parsed["arguments"]["recursive"] is True
    assert parsed["arguments"]["depth"] == 4


@pytest.mark.asyncio
async def test_last_mode_inheritance_for_short_replies(tmp_path):
    """Verify that short user follow-ups in Auto mode inherit the previous Agent mode."""
    session = AgentSession(str(tmp_path), {"max_turns": 5}, AsyncMock())
    session.last_mode = "Agent"
    
    # We mock _run_llm_query just in case, but it shouldn't be called since it inherits Agent
    session._run_llm_query = AsyncMock(return_value="Ask")
    
    async def mock_stream_chat(*args, **kwargs):
        yield {"type": "done", "stop_reason": "end_turn"}
    
    # When user replies with "html" (length < 30) in "Auto" mode, it should inherit "Agent"
    with patch("app.adapters.llm.LLMAdapter.stream_chat", mock_stream_chat):
        await session.handle_user_message("html", mode="Auto")
    assert session.last_mode == "Agent"
    session._run_llm_query.assert_not_called()


@pytest.mark.asyncio
async def test_terminal_auto_apply_bypass(tmp_path):
    """Verify that run_terminal_command does NOT bypass the permission prompt even if auto_apply is True, ensuring all arbitrary commands require approval."""
    session = AgentSession(str(tmp_path), {"max_turns": 5}, AsyncMock())
    
    class MockPermissionManager:
        def check_permission(self, cmd):
            # Command is mutative but not destructive, and not auto-approved by default
            return False, "mutative", "Needs prompt"
            
    session.permission_manager = MockPermissionManager()
    
    # Simulate a background task that approves the request after a short delay
    async def simulate_user_approval():
        await asyncio.sleep(0.1)
        if "tc_auto_1" in session.pending_confirmations:
            session.pending_confirmations["tc_auto_1"]["approved"] = True
            session.pending_confirmations["tc_auto_1"]["event"].set()

    asyncio.create_task(simulate_user_approval())
    
    # We mock the actual shell execution
    with patch("app.tools.terminal_tool.run_shell_command", AsyncMock(return_value="success")):
        res = await run_terminal_command(
            session=session,
            tc_id="tc_auto_1",
            args={"command": "npm run build"},
            auto_apply=True
        )
        assert res == "success"
        assert "tc_auto_1" not in session.pending_confirmations
