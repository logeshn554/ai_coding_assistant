import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.orchestrator import (
    AgentOrchestrator,
    RequirementAnalysisAgent,
    orchestrator_node,
    AgentState
)

@pytest.mark.asyncio
async def test_requirement_analysis_for_new_project(tmp_path):
    """Verify Requirement Analysis Agent identifies new files to create when workspace is empty."""
    orchestrator = MagicMock()
    orchestrator.context = MagicMock()
    orchestrator.context.log = AsyncMock()
    orchestrator.context.memory = {}
    orchestrator.update_task_progress = AsyncMock()
    
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "test_key",
        "base_url": "http://test",
        "model_name": "gpt-4o"
    }
    session.workspace_root = str(tmp_path)
    
    agent = RequirementAnalysisAgent(orchestrator)
    
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = '["index.html"]'
        
        result = await agent.execute("create a flappy bird game in a single HTML file", session, 1)
        assert result == "Completed"
        assert orchestrator.context.memory["target_files"] == ["index.html"]

@pytest.mark.asyncio
async def test_orchestrator_routes_to_coding_agent_on_empty_workspace():
    """Verify Orchestrator allows calling Coding/Frontend Agent when target_files has new files even if file_contents is empty."""
    orchestrator = MagicMock()
    orchestrator.agents = {
        "Requirement Analysis Agent": MagicMock(),
        "File System Agent": MagicMock(),
        "Frontend Developer Agent": MagicMock(),
        "Coding Agent": MagicMock()
    }
    
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "test_key",
        "base_url": "http://test",
        "model_name": "gpt-4o"
    }
    session.send_ws_message = AsyncMock()
    
    state: AgentState = {
        "task_description": "create a flappy bird game in a single HTML file",
        "collaboration_log": [
            "Requirement Analysis Agent: Identified target files: ['index.html']",
            "File System Agent: Read codebase files..."
        ],
        "memory": {
            "target_files": ["index.html"],
            "file_contents": {}  # Intentionally empty for new project!
        },
        "subtasks": [],
        "active_agent": "Orchestrator",
        "active_task": "",
        "next_agents": [],
        "agent_tasks": {},
        "session": session,
        "task_id_counter": 1,
        "step_count": 0,
        "orchestrator": orchestrator
    }
    
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = '{"agents": ["Frontend Developer Agent"], "reasoning": "New project creation: target_files specified", "descriptions": ["Create flappy bird game in index.html"]}'
        
        new_state = await orchestrator_node(state)
        assert "Frontend Developer Agent" in new_state["next_agents"]

@pytest.mark.asyncio
async def test_frontend_developer_agent_writes_file(tmp_path):
    """Verify FrontendDeveloperAgent receives target file and writes it."""
    orchestrator = MagicMock()
    orchestrator.context = MagicMock()
    orchestrator.context.log = AsyncMock()
    orchestrator.context.memory = {
        "target_files": ["index.html"],
        "file_contents": {}
    }
    orchestrator.update_task_progress = AsyncMock()
    
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "test_key",
        "base_url": "http://test",
        "model_name": "gpt-4o"
    }
    session.workspace_root = str(tmp_path)
    session._execute_tool_with_guardrails = AsyncMock(return_value="File written successfully")
    session.send_ws_message = AsyncMock()
    
    from app.orchestrator import FrontendDeveloperAgent
    agent = FrontendDeveloperAgent(orchestrator)
    
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = "<!DOCTYPE html><html><head><title>Flappy Bird</title></head><body><canvas id='game'></canvas></body></html>"
        
        result = await agent.execute("create a flappy bird game in a single HTML file", session, 1)
        assert result == "Frontend components implemented."
        assert session._execute_tool_with_guardrails.call_count == 1
        call_args = session._execute_tool_with_guardrails.call_args[0]
        assert call_args[1] == "write_file"
        assert call_args[2]["path"] == "index.html"
        assert "Flappy Bird" in call_args[2]["content"]

@pytest.mark.asyncio
async def test_e2e_create_flappy_bird(tmp_path):
    """E2E test verifying 'create a flappy bird game in a single HTML file' calls FrontendDeveloperAgent and writes index.html."""
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "test_key",
        "base_url": "http://test",
        "model_name": "gpt-4o"
    }
    session.workspace_root = str(tmp_path)
    session.send_ws_message = AsyncMock()
    session.conversation_history = []
    session._execute_tool_with_guardrails = AsyncMock(return_value="File written successfully")

    orchestrator = AgentOrchestrator()

    # ModelRouter completion mock responses dynamically:
    # 1. Requirement Analysis Agent -> returns ['index.html']
    # 2. Planner Agent -> returns a single subtask plan for Frontend Developer Agent
    # 3. Frontend Developer Agent -> returns HTML code
    # 4. Summarize (Orchestrator Agent) -> returns final summary
    async def dynamic_completion(*args, **kwargs):
        task_type = args[4] if len(args) > 4 else kwargs.get("task_type", "")
        task_type_lower = (task_type or "").lower()
        
        messages = args[1] if len(args) > 1 else kwargs.get("messages", [])
        user_msg = messages[-1]["content"].lower() if messages else ""
        system_prompt = args[2] if len(args) > 2 else kwargs.get("system_prompt", "")
        sys_prompt_lower = (system_prompt or "").lower()
        
        if "planner" in task_type_lower or ("planner" in sys_prompt_lower and "requirement" not in sys_prompt_lower):
            return '[{"id": 1, "agent": "Frontend Developer Agent", "description": "create flappy bird", "dependencies": []}]'
        elif "requirement" in task_type_lower or "requirement" in sys_prompt_lower:
            return '["index.html"]'
        elif "frontend" in task_type_lower or "frontend" in sys_prompt_lower:
            return '<!DOCTYPE html><html><head><title>Flappy Bird</title></head><body><h1>Flappy Bird</h1></body></html>'
        elif "summarize" in sys_prompt_lower or "summary" in task_type_lower:
            return 'Created flappy bird game in index.html'
        else:
            return "Success/Completed"

    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.side_effect = dynamic_completion
        try:
            res = await orchestrator.run_task("create a flappy bird game in a single HTML file", session)
        except Exception as ex:
            print("RUN TASK EXCEPTION:", type(ex), ex)
            raise ex
        print("CALL COUNT:", mock_completion.call_count)
        for i, c in enumerate(mock_completion.call_args_list):
            kw = {k: str(v).encode('ascii', 'ignore').decode('ascii') for k, v in c[1].items()}
            print(f"CALL {i}: kwargs={kw}")
        print("FULL COLLAB LOG:")
        for log in orchestrator.context.collaboration_log:
            print("  LOG:", log.encode('ascii', 'ignore').decode('ascii'))
        assert mock_completion.call_count >= 5
        calls = [c for c in session._execute_tool_with_guardrails.call_args_list if c[0][1] == "write_file"]
        assert len(calls) >= 1
        assert calls[0][0][2]["path"] == "index.html"
        assert "Flappy Bird" in calls[0][0][2]["content"]

