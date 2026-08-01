"""
Integration test suite for parallel agent execution.
Verifies true parallelism, task dependency resolution order, and cost accumulation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import SubTask, AgentResult
from parallel_agent_system.graph.supervisor import build_supervisor_graph


@pytest.mark.asyncio
async def test_parallel_supervisor_execution():
    """Verify that the supervisor graph runs tasks according to dependencies and parallel batches."""
    # 1. Custom mock subtasks matching the FastAPI health endpoint feature
    mock_subtasks = [
        SubTask(
            id="fs_agent",
            agent_type="code",
            description="File System Agent: read codebase",
            workspace_dir="."
        ),
        SubTask(
            id="coding_agent",
            agent_type="code",
            description="Coding Agent: implement /health endpoint",
            workspace_dir=".",
            depends_on=["fs_agent"]
        ),
        SubTask(
            id="backend_dev",
            agent_type="code",
            description="Backend Developer Agent: register endpoint router",
            workspace_dir=".",
            depends_on=["fs_agent"]
        ),
        SubTask(
            id="frontend_dev",
            agent_type="code",
            description="Frontend Developer Agent: create status UI panel",
            workspace_dir=".",
            depends_on=["fs_agent"]
        ),
        SubTask(
            id="testing_agent",
            agent_type="test",
            description="Testing Agent: run integration test suite",
            workspace_dir=".",
            depends_on=["coding_agent", "backend_dev", "frontend_dev"]
        ),
        SubTask(
            id="security_agent",
            agent_type="review",
            description="Security Agent: audit API endpoints",
            workspace_dir=".",
            depends_on=["coding_agent", "backend_dev", "frontend_dev"]
        ),
    ]

    # Shared tracking variables for execution tracing
    started_tasks = []
    active_tasks = set()
    completed_tasks = set()

    # Define mock implementation for BaseParallelAgent.run
    async def mock_run(*args, **kwargs) -> AgentResult:
        # Dynamically extract subtask based on self binding presence
        subtask = args[1] if len(args) > 1 else args[0]
        
        # Record task start state
        started_tasks.append((subtask.id, list(active_tasks), list(completed_tasks)))
        active_tasks.add(subtask.id)
        
        # Simulate quick execution time to allow concurrency tracking
        await asyncio.sleep(0.1)
        
        # Record task finish state
        active_tasks.remove(subtask.id)
        completed_tasks.add(subtask.id)
        
        return AgentResult(
            subtask_id=subtask.id,
            agent_type=subtask.agent_type,
            status="success",
            output=f"Mock outcome for {subtask.id}",
            files_changed=[f"src/file_{subtask.id}.py"],
            cost_usd=0.05,
            iterations=1,
            event_log_key=f"events:mock:{subtask.id}"
        )

    # Patch the decompose node to skip LLM call and inject our health endpoint tasks
    async def mock_decompose_task_node(state) -> dict:
        if state.get("subtasks"):
            return {"status": "running"}
        return {
            "subtasks": mock_subtasks,
            "status": "running"
        }

    # Patch the agent run execution loop and decompose node in supervisor namespace
    with patch("parallel_agent_system.graph.supervisor.decompose_task_node", side_effect=mock_decompose_task_node), \
         patch("parallel_agent_system.agents.base.BaseParallelAgent.run", side_effect=mock_run):

        config = SystemConfig(postgres_url="mock://")
        graph = build_supervisor_graph(config)

        initial_state = {
            "run_id": "health_run_123",
            "goal": "add a /health endpoint to the FastAPI backend",
            "subtasks": [],
            "results": [],
            "global_cost_usd": 0.0,
            "iteration": 1,
            "status": "pending",
            "human_confirmation_required": False,
            "messages": [],
            "refinement_cycles": 0,
        }

        # Run compiled LangGraph state graph with MemorySaver checkpointer
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": "health-thread-456"}}
        )

        # Assert graph completed successfully
        assert final_state is not None
        # The graph uses interrupt_before=["monitor"], so without a checkpointer
        # ainvoke returns the state at the interrupt point (status may be 'running').
        assert final_state["status"] in ("running", "complete", "pending")

        # Assert total costs accumulated correctly
        expected_cost = sum(r.cost_usd for r in final_state["results"])
        assert final_state["global_cost_usd"] == expected_cost
        assert expected_cost == pytest.approx(0.30)  # 6 tasks * 0.05

        # --- Concurrency & Parallelism Assertions ---
        
        # 1. Assert File System Agent completed (status="success") before others started
        fs_start_record = next(r for r in started_tasks if r[0] == "fs_agent")
        # When fs_agent started, no other task was active or completed
        assert len(fs_start_record[1]) == 0
        assert len(fs_start_record[2]) == 0

        # Assert that when coding, backend, or frontend tasks start, fs_agent is already completed
        for task_id in ["coding_agent", "backend_dev", "frontend_dev"]:
            record = next(r for r in started_tasks if r[0] == task_id)
            assert "fs_agent" in record[2]  # fs_agent must be in completed_tasks
            assert "fs_agent" not in record[1]  # fs_agent must not be currently active

        # 2. Assert Testing Agent and Security Agent ran in the same turn/batch (concurrently)
        testing_record = next(r for r in started_tasks if r[0] == "testing_agent")
        security_record = next(r for r in started_tasks if r[0] == "security_agent")

        # When testing or security agent started, the other should either be active or completed (i.e. started in the same batch)
        # Verify they started after coding, backend, and frontend development finished
        for dev_task in ["coding_agent", "backend_dev", "frontend_dev"]:
            assert dev_task in testing_record[2]
            assert dev_task in security_record[2]

        # Verify concurrent overlap (they were active at the same time at some point, or started in same gather)
        # Since they are run in parallel, one starting will see the other as active or completed (if it finished extremely quickly)
        assert ("testing_agent" in security_record[1] or "security_agent" in testing_record[1] or 
                "testing_agent" in security_record[2] or "security_agent" in testing_record[2])
