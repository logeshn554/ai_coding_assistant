import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.orchestrator import AgentOrchestrator, AgentState, orchestrator_node, make_agent_node, route_next

@pytest.mark.asyncio
async def test_langgraph_nodes_and_routing():
    # Mock orchestrator and session
    orchestrator = MagicMock()
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "test_key",
        "base_url": "http://test",
        "model_name": "gpt-4o"
    }
    session.send_ws_message = AsyncMock()
    
    # Initialize basic state (matching AgentState definition)
    state: AgentState = {
        "task_description": "test query",
        "collaboration_log": [],
        "memory": {},
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
    
    # Patch ModelRouter.completion to return a valid JSON routing decision
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = '{"agents": ["Orchestrator"], "reasoning": "Done", "descriptions": ["Done"]}'
        
        # Test orchestrator node decision
        new_state = await orchestrator_node(state)
        assert new_state["next_agents"] == ["Orchestrator"]
        assert new_state["step_count"] == 1
        
        # Test route next logic
        route = route_next(new_state)
        assert route in (["end"], "end")

@pytest.mark.asyncio
async def test_parallel_coding_agent(tmp_path):
    orchestrator = MagicMock()
    orchestrator.context = MagicMock()
    orchestrator.context.log = AsyncMock()
    orchestrator.update_task_progress = AsyncMock()
    orchestrator.event_bus = MagicMock()
    orchestrator.event_bus.emit = AsyncMock()
    orchestrator.context.memory = {
        "target_files": ["file1.py", "file2.py"],
        "file_contents": {
            "file1.py": "def foo(): pass",
            "file2.py": "def bar(): pass"
        }
    }
    
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "test_key",
        "base_url": "http://test",
        "model_name": "gpt-4o"
    }
    session.workspace_root = str(tmp_path)
    session._execute_tool_with_guardrails = AsyncMock(return_value="success")
    session.send_ws_message = AsyncMock()
    
    from app.orchestrator import CodingAgent
    agent = CodingAgent(orchestrator)
    
    # Patch ModelRouter.completion to return generated code response
    with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_completion:
        mock_completion.return_value = "def modified(): pass"
        
        # Execute coding agent
        result = await agent.execute("refactor codebase", session, 1)
        assert result == "Completed"
        
        # Verify both tool calls were invoked
        assert session._execute_tool_with_guardrails.call_count == 2
