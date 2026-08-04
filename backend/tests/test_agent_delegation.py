"""Tests for delegate_to_agent tool integration and concurrency in session loop."""

from __future__ import annotations

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# Ensure backend root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.session.agent_session import AgentSession
from app.tools.dispatcher import dispatch_tool
from app.adapters.base import AVAILABLE_TOOLS

class MockOrchestratorContext:
    def __init__(self):
        self.collaboration_log = []
        self.lock = AsyncMock()

    async def log(self, msg: str):
        self.collaboration_log.append(msg)

class MockOrchestrator:
    def __init__(self):
        self.context = MockOrchestratorContext()
        self.agents = {}

class MockSession:
    def __init__(self):
        self.workspace_root = "/fake/workspace"
        self.profile = {
            "api_key": "test_key",
            "base_url": "http://localhost",
            "model_name": "test-model",
            "max_turns": 5,
        }
        self.orchestrator = MockOrchestrator()
        self.conversation_history = []
        self.max_turns = 5
        self.auto_apply = False
        self.is_running = False
        self.parallel_subtasks = []
        self.collaboration_log = []

    async def send_ws_message(self, msg):
        pass

    async def _stream_chat_wrapper(self, adapter, messages, tools, system_prompt):
        async for chunk in adapter.stream_chat(messages, tools, system_prompt):
            yield chunk

    async def _execute_tool_with_guardrails(self, tc_id, tc_name, tc_args, auto_apply):
        return await dispatch_tool(self, tc_id, tc_name, tc_args, auto_apply)

    def _get_adapter(self, is_agent=False):
        adapter = MagicMock()
        adapter.stream_chat = self._fake_stream
        return adapter

    def _get_system_prompt(self, mode):
        return "System Prompt"

    def _get_tools_for_mode(self, mode):
        # Use the actual AgentSession._get_tools_for_mode implementation
        return AgentSession._get_tools_for_mode(self, mode)

    async def save_history_to_db(self):
        pass

    def _trim_history_for_context(self, history, system_prompt, tools, max_chars=20000):
        return history


@pytest.mark.asyncio
async def test_delegate_to_agent_success():
    session = MockSession()
    
    # Mock a specialist agent
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value="Finished successfully")
    session.orchestrator.agents["Testing Agent"] = mock_agent

    # Test dispatching to agent
    result = await dispatch_tool(
        session,
        "tc-1",
        "delegate_to_agent",
        {"agent_name": "Testing Agent", "task_description": "Run unit tests"},
        auto_apply=True
    )
    
    assert result == "Finished successfully"
    mock_agent.execute.assert_called_once_with("Run unit tests", session, 1)
    assert "Testing Agent: Finished successfully" in session.orchestrator.context.collaboration_log


@pytest.mark.asyncio
async def test_delegate_to_agent_case_insensitive_success():
    session = MockSession()
    
    # Mock a specialist agent
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value="Finished successfully")
    session.orchestrator.agents["Testing Agent"] = mock_agent

    # Test case-insensitive dispatching (e.g. lowercase)
    result = await dispatch_tool(
        session,
        "tc-1",
        "delegate_to_agent",
        {"agent_name": "testing agent", "task_description": "Run unit tests"},
        auto_apply=True
    )
    
    assert result == "Finished successfully"
    mock_agent.execute.assert_called_once_with("Run unit tests", session, 1)


@pytest.mark.asyncio
async def test_delegate_to_agent_unknown_agent():
    session = MockSession()
    session.orchestrator.agents["Testing Agent"] = MagicMock()

    result = await dispatch_tool(
        session,
        "tc-1",
        "delegate_to_agent",
        {"agent_name": "Unknown Agent", "task_description": "Do something"},
        auto_apply=True
    )
    
    assert "ERROR: Unknown agent 'Unknown Agent'" in result
    assert "Testing Agent" in result


@pytest.mark.asyncio
async def test_delegate_to_agent_domain_fallback():
    session = MockSession()
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value="Game built successfully")
    session.orchestrator.agents["Frontend Developer Agent"] = mock_agent

    result = await dispatch_tool(
        session,
        "tc-1",
        "delegate_to_agent",
        {"agent_name": "Game Development Agent", "task_description": "Create Flappy Bird"},
        auto_apply=True
    )

    assert result == "Game built successfully"
    mock_agent.execute.assert_called_once_with("Create Flappy Bird", session, 1)



@pytest.mark.asyncio
async def test_agent_session_tool_calling_loop():
    session = MockSession()
    
    # Mock agent
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value="Tests passed")
    session.orchestrator.agents["Testing Agent"] = mock_agent

    # Define fake LLM stream that emits a delegate_to_agent tool call
    call_count = 0
    async def fake_stream(messages, tools, system_prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "type": "tool_call",
                "id": "tc_delegate_01",
                "name": "delegate_to_agent",
                "input": {
                    "agent_name": "Testing Agent",
                    "task_description": "Verify code changes"
                }
            }
            yield {"type": "done", "stop_reason": "tool_use"}
        else:
            yield {"type": "text", "content": "Orchestrator: All done."}
            yield {"type": "done", "stop_reason": "stop"}

    session._fake_stream = fake_stream

    # Call actual handle_user_message through standard AgentSession
    with patch("app.session.agent_session.AgentSession._get_adapter") as mock_get_adapter:
        mock_get_adapter.return_value = session._get_adapter()
        
        # Invoke handle_user_message on a mock instance using original implementation
        await AgentSession.handle_user_message(session, "run tests", "Agent", auto_apply=True)

    # Asserts:
    # 1. Testing Agent was executed
    mock_agent.execute.assert_called_once_with("Verify code changes", session, 1)
    
    # 2. Tool result got sent back to conversation history
    tool_entry = next((m for m in session.conversation_history if m.get("role") == "tool"), None)
    assert tool_entry is not None
    assert tool_entry["tool_call_id"] == "tc_delegate_01"
    assert tool_entry["content"] == "Tests passed"


def test_tools_filtered_for_mode():
    session = MockSession()
    
    # In Ask mode, delegate_to_agent should NOT be in the tools
    ask_tools = session._get_tools_for_mode("Ask")
    assert not any(t["name"] == "delegate_to_agent" for t in ask_tools)

    # In Plan mode, delegate_to_agent should NOT be in the tools
    plan_tools = session._get_tools_for_mode("Plan")
    assert not any(t["name"] == "delegate_to_agent" for t in plan_tools)

    # In Agent mode, delegate_to_agent SHOULD be in the tools
    agent_tools = session._get_tools_for_mode("Agent")
    assert any(t["name"] == "delegate_to_agent" for t in agent_tools)


def test_system_prompt_appends_collaboration_log_and_memory(tmp_path):
    session = MockSession()
    session.workspace_root = str(tmp_path)
    session.orchestrator.context.collaboration_log = ["First task run", "Second task run"]
    session.orchestrator.context.memory = {"target_files": ["a.py"], "some_state": 123}

    # Call actual _get_system_prompt through standard AgentSession
    prompt = AgentSession._get_system_prompt(session, "Agent")
    
    # Assert collaboration log is included
    assert "Collaboration Log:" in prompt
    assert "- First task run" in prompt
    assert "- Second task run" in prompt

    # Assert shared memory is included
    assert "Shared Memory:" in prompt
    assert '"target_files": [\n    "a.py"\n  ]' in prompt
    assert '"some_state": 123' in prompt


@pytest.mark.asyncio
async def test_all_23_orchestrator_agents_execute(tmp_path):
    from app.orchestrator import AgentOrchestrator
    
    orchestrator = AgentOrchestrator()
    session = MockSession()
    session.workspace_root = str(tmp_path)
    
    # Create some dummy files in workspace so Requirement Analysis / File System / chunking agents don't fail
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}', encoding="utf-8")
    
    session.orchestrator = orchestrator
    
    # Preset shared memory
    orchestrator.context.memory["target_files"] = ["app.py"]
    orchestrator.context.memory["file_contents"] = {"app.py": "print('hello')"}
    
    # Mock ModelRouter.completion to return different values depending on the agent
    async def mock_completion(*args, **kwargs):
        # Determine the task type based on the task description or other signature
        msg = str(args) + str(kwargs)
        msg_l = msg.lower()
        if "planner" in msg_l:
            return '[{"id": 1, "agent": "Coding Agent", "description": "mock task", "dependencies": []}]'
        elif "requirement" in msg_l:
            return '["app.py"]'
        elif "orchestrator" in msg_l:
            return '{"agents": ["Coding Agent"], "reasoning": "mock reasoning", "descriptions": ["mock task"]}'
        else:
            return "Mock agent response content"
            
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
        mock_comp.side_effect = mock_completion
        
        # Patch any terminal runner commands
        with patch("app.tools.terminal_tool.run_shell_command", new_callable=AsyncMock) as mock_shell:
            mock_shell.return_value = "git version 2.40"
            
            # Mock _execute_tool_with_guardrails to return a generic success
            session._execute_tool_with_guardrails = AsyncMock(return_value="success")
            
            # Now execute all 23 agents
            for agent_name, agent in orchestrator.agents.items():
                print(f"Testing execution of {agent_name}...")
                result = await agent.execute("Implement user dashboard", session, task_id=123)
                assert result is not None


@pytest.mark.asyncio
async def test_agent_output_handlers_and_json_parsing():
    from app.orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator()
    session = MockSession()
    session.orchestrator = orchestrator
    session.workspace_root = "./"
    
    # 1. Test PlannerAgent JSON parser and subtask listing
    planner = session.orchestrator.agents["Planner Agent"]
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
        mock_comp.return_value = '```json\n[{"id": 1, "agent": "Coding Agent", "description": "Write index.html", "dependencies": []}]\n```'
        result = await planner.execute("Build flappy bird", session, task_id=1)
        assert "Plan formulated" in result
        assert len(session.orchestrator.context.subtasks) == 1
        assert session.orchestrator.context.subtasks[0]["agent"] == "Coding Agent"

    # 2. Test RequirementAnalysisAgent report writing and files extraction
    researcher = session.orchestrator.agents["Requirement Analysis Agent"]
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
        mock_comp.return_value = '{\n  "report": "# Test findings\\nEverything looks clean.",\n  "target_files": ["app.py", "tests.py"]\n}'
        
        # Mock file write
        mock_open_file = mock_open()
        with patch("builtins.open", mock_open_file):
            result = await researcher.execute("Analyze auth requirements", session, task_id=2)
            assert result == "Completed"
            mock_open_file.assert_any_call(os.path.join(session.workspace_root, "RESEARCH_REPORT.md"), "w", encoding="utf-8")
            # Verify writing occurred on the opened file handle
            handle = mock_open_file()
            handle.write.assert_any_call("# Test findings\nEverything looks clean.")
            assert session.orchestrator.context.memory["target_files"] == ["app.py", "tests.py"]

    # 3. Test CodingAgent JSON files writing
    coder = session.orchestrator.agents["Coding Agent"]
    session.orchestrator.context.memory["target_files"] = ["index.html"]
    session.orchestrator.context.memory["file_contents"] = {"index.html": ""}
    
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
        mock_comp.return_value = '{\n  "files": [\n    {\n      "path": "index.html",\n      "content": "<!DOCTYPE html><html></html>"\n    }\n  ]\n}'
        session._execute_tool_with_guardrails = AsyncMock(return_value="File written")
        
        result = await coder.execute("Generate HTML page", session, task_id=3)
        assert result == "Completed"
        session._execute_tool_with_guardrails.assert_called_once()
        args = session._execute_tool_with_guardrails.call_args[0]
        assert args[1] == "write_file"
        assert args[2]["path"] == "index.html"
        assert args[2]["content"] == "<!DOCTYPE html><html></html>"

    # 4. Test DebuggingAgent JSON fixes overwriting
    debugger = session.orchestrator.agents["Debugging Agent"]
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
        mock_comp.return_value = '{\n  "explanation": "Fixed syntax error",\n  "fixes": [\n    {\n      "path": "app.py",\n      "content": "print(\'fixed\')"\n    }\n  ]\n}'
        session._execute_tool_with_guardrails = AsyncMock(return_value="File written")
        
        result = await debugger.execute("Fix python file", session, task_id=4)
        assert result == "Completed"
        assert session.orchestrator.context.memory["debugging_notes"] == "Fixed syntax error"
        session._execute_tool_with_guardrails.assert_called_once()
        args = session._execute_tool_with_guardrails.call_args[0]
        assert args[1] == "write_file"
        assert args[2]["path"] == "app.py"
        assert args[2]["content"] == "print('fixed')"

    # 5. Test TerminalAgent commands execution
    terminal = session.orchestrator.agents["Terminal Agent"]
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
        mock_comp.return_value = '{\n  "commands": ["pytest", "npm test"]\n}'
        with patch("app.tools.terminal_tool.run_shell_command", new_callable=AsyncMock) as mock_shell:
            mock_shell.return_value = "Tests passed successfully"
            result = await terminal.execute("Verify all tests pass", session, task_id=5)
            assert result == "Completed"
            assert mock_shell.call_count == 2
            mock_shell.assert_any_call(session, "pytest")
            mock_shell.assert_any_call(session, "npm test")

