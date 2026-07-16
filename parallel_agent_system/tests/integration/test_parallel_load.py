"""
Integration test to validate graph execution concurrency and thread state isolation.
Simulates concurrent sessions to ensure the Redis pool and LangGraph memory checkpointer
do not saturate or collide under load.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import asyncio
import pytest
from unittest.mock import patch, MagicMock
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import SubTask, AgentResult
from parallel_agent_system.graph.supervisor import build_supervisor_graph


@pytest.mark.asyncio
async def test_concurrent_sessions_load():
    """Verify that multiple concurrent graph invocations with unique thread_ids resolve cleanly under load."""
    # 5 tasks that will run sequentially but across 5 concurrent graph runs
    subtasks = [
        SubTask(id="task_A", agent_type="code", description="Task A", workspace_dir="."),
        SubTask(id="task_B", agent_type="test", description="Task B", workspace_dir=".", depends_on=["task_A"])
    ]

    async def mock_run(*args, **kwargs) -> AgentResult:
        subtask = args[1] if len(args) > 1 else args[0]
        # Simulate variable concurrent processing delays
        await asyncio.sleep(0.05)
        return AgentResult(
            subtask_id=subtask.id,
            agent_type=subtask.agent_type,
            status="success",
            output=f"Outcome for {subtask.id}",
            files_changed=[f"src/file_{subtask.id}.py"],
            cost_usd=0.01,
            iterations=1,
            event_log_key=f"events:mock:{subtask.id}"
        )

    async def mock_decompose(state) -> dict:
        if state.get("subtasks"):
            return {"status": "running"}
        return {
            "subtasks": subtasks,
            "status": "running"
        }

    # Execute all 5 graph runs concurrently
    with patch("parallel_agent_system.graph.supervisor.decompose_task_node", side_effect=mock_decompose), \
         patch("parallel_agent_system.agents.base.BaseParallelAgent.run", side_effect=mock_run):
         
        config = SystemConfig(postgres_url="mock://")
        graph = build_supervisor_graph(config)

        # Setup 5 concurrent runner coroutines
        async def run_single_session(session_idx: int):
            initial_state = {
                "run_id": f"load_run_{session_idx}",
                "goal": f"Concurrent load test objective {session_idx}",
                "subtasks": [],
                "results": [],
                "global_cost_usd": 0.0,
                "iteration": 1,
                "status": "pending",
                "human_confirmation_required": False,
                "messages": []
            }
            
            final_state = await graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": f"load-thread-{session_idx}"}}
            )
            return final_state

        tasks = [run_single_session(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify all sessions resolved successfully
        assert len(results) == 5
        for res in results:
            assert res is not None
            assert res["status"] == "complete"
            assert len(res["results"]) == 2
            assert res["global_cost_usd"] == pytest.approx(0.02)
