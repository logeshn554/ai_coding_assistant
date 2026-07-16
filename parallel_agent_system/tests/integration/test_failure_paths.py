"""
Integration test suite for system failure scenarios.
Covers orchestrator routing failures, reduce/monitor node subtask failures,
log summarisation fallback, and subprocess command execution timeouts.
"""

import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.app.orchestrator import orchestrator_node, maybe_summarise_log

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import SubTask, AgentResult
from parallel_agent_system.graph.supervisor import reduce_node, monitor_node


@pytest.mark.asyncio
async def test_orchestrator_node_routes_debugging_on_failure():
    """Verify that when a subtask is marked failed, orchestrator chooses Debugging Agent next."""
    mock_session = MagicMock()
    mock_session.send_ws_message = AsyncMock()
    mock_orchestrator = MagicMock()
    
    # Mock LLM decision response routing to Debugging Agent
    mock_decision_json = '{"reasoning": "Subtask failed, routing to Debugging Agent.", "agents": ["Debugging Agent"], "descriptions": ["Fix the failing subtask"]}'
    mock_response = MagicMock(content=mock_decision_json)
    
    initial_state = {
        "task_description": "Fix /health endpoint issues",
        "collaboration_log": ["Orchestrator: Subtask test_agent returned failed"],
        "memory": {},
        "subtasks": [
            {"id": 1, "agent": "Testing Agent", "status": "failed", "description": "run integration tests"}
        ],
        "active_agent": "Orchestrator",
        "active_task": "Deciding next agent...",
        "next_agents": ["Orchestrator"],
        "agent_tasks": {},
        "session": mock_session,
        "task_id_counter": 2,
        "step_count": 0,
        "orchestrator": mock_orchestrator
    }
    
    with patch("backend.app.orchestrator.DevPilotChatModel.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_response
        
        final_state = await orchestrator_node(initial_state)
        
        assert "Debugging Agent" in final_state["next_agents"]
        assert final_state["agent_tasks"]["Debugging Agent"] == "Fix the failing subtask"


@pytest.mark.asyncio
async def test_reduce_and_monitor_node_failing_status():
    """Verify reduce_node and monitor_node change graph status to failed on failure."""
    subtasks = [
        SubTask(id="task1", agent_type="code", description="write code", workspace_dir=".")
    ]
    results = [
        AgentResult(
            subtask_id="task1",
            agent_type="code",
            status="failed",
            output="Error running compiler",
            event_log_key="events:mock"
        )
    ]
    
    # Run reduce node
    reduce_state = {
        "subtasks": subtasks,
        "results": results,
        "global_cost_usd": 0.0
    }
    reduce_out = await reduce_node(reduce_state)
    assert reduce_out["status"] == "running"  # reduce_node routes to monitor as running or failed if conflict
    
    # Run monitor node with iteration beyond limit to trigger fail state
    config = SystemConfig()
    monitor_state = {
        "subtasks": subtasks,
        "results": results,
        "global_cost_usd": reduce_out["global_cost_usd"],
        "iteration": config.max_retries + 1,
        "status": "running"
    }
    monitor_out = await monitor_node(monitor_state)
    assert monitor_out["status"] == "failed"


@pytest.mark.asyncio
async def test_maybe_summarise_log_preserves_log_on_llm_failure():
    """Verify that maybe_summarise_log keeps raw logs intact if the LLM summarizer throws."""
    mock_session = MagicMock()
    mock_session.profile = {}
    mock_session.collaboration_log = []
    
    # Build 12 log entries
    original_log = [f"Step {i}: executed some work" for i in range(12)]
    state = {
        "collaboration_log": list(original_log),
        "session": mock_session
    }
    
    # Mock ModelRouter to raise an exception
    with patch("backend.app.adapters.router.ModelRouter.completion", side_effect=Exception("API connection timeout")):
        final_state = await maybe_summarise_log(state, mock_session)
        
        # Log should not be lost; must retain all 12 original entries
        assert len(final_state["collaboration_log"]) == 12
        assert final_state["collaboration_log"] == original_log


@pytest.mark.asyncio
async def test_run_shell_command_timeout_emits_failed_status():
    """Verify that when _run_shell_command times out, it emits terminal_status failed."""
    from backend.app.agent import AgentSession
    
    mock_orchestrator = MagicMock()
    mock_orchestrator.max_steps = 30
    
    # Track WS messages sent
    ws_messages = []
    async def mock_send_ws(msg):
        ws_messages.append(msg)
        
    # Create AgentSession instance
    agent_instance = AgentSession(
        workspace_root=".",
        profile={},
        send_ws_message=mock_send_ws
    )
    agent_instance.orchestrator = mock_orchestrator
    
    # Mock create_subprocess_exec to trigger asyncio.TimeoutError
    async def mock_subprocess(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        # Mock readline to raise TimeoutError
        async def mock_readline():
            raise asyncio.TimeoutError()
        mock_proc.stdout.readline = mock_readline
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess), \
         patch("backend.app.processes.confine_subprocess", return_value=None), \
         patch("sys.platform", "win32"), \
         patch("subprocess.call", return_value=0):
         
        res = await agent_instance._run_shell_command("sleep 35")
        
        assert "timed out after 30 seconds" in res
            
        # Assert the failed terminal status message was emitted
        assert any(
            msg.get("type") == "terminal_status" and msg.get("status") == "failed"
            for msg in ws_messages
        )
