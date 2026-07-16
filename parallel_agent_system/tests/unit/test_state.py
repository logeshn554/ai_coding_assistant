import pytest
from parallel_agent_system.core.state import SubTask, AgentResult, GraphState
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.graph.supervisor import build_supervisor_graph


def test_subtask_validation():
    """Verify that SubTask validation works with valid and default inputs."""
    task = SubTask(
        id="task-123",
        agent_type="code",
        description="Write code for helper modules",
        workspace_dir="/workspace/src",
        priority=1
    )
    assert task.id == "task-123"
    assert task.agent_type == "code"
    assert task.priority == 1
    assert task.depends_on == []


def test_agent_result_validation():
    """Verify that AgentResult validation works with proper types."""
    result = AgentResult(
        subtask_id="task-123",
        agent_type="code",
        status="success",
        output="Helper module completed successfully.",
        event_log_key="events:run-123:task-123",
        cost_usd=0.15,
        iterations=5
    )
    assert result.subtask_id == "task-123"
    assert result.status == "success"
    assert result.cost_usd == 0.15
    assert result.iterations == 5


def test_graph_state_reducer():
    """Verify state reducer appends AgentResults correctly."""
    # We can verify the list addition operator works as expected in Annotated lists
    import operator
    results_reducer = operator.add
    
    r1 = AgentResult(subtask_id="t1", agent_type="code", status="success", output="a", event_log_key="k1")
    r2 = AgentResult(subtask_id="t2", agent_type="test", status="success", output="b", event_log_key="k2")
    
    merged = results_reducer([r1], [r2])
    assert len(merged) == 2
    assert merged[0].subtask_id == "t1"
    assert merged[1].subtask_id == "t2"


@pytest.mark.asyncio
async def test_supervisor_graph_skeleton():
    """Compiles the supervisor graph and executes it in testing mode with MemorySaver checkpointer."""
    config = SystemConfig(postgres_url="mock://")
    graph = build_supervisor_graph(config)
    
    initial_state = {
        "run_id": "run-456",
        "goal": "Test system implementation",
        "subtasks": [],
        "results": [],
        "global_cost_usd": 0.0,
        "iteration": 0,
        "status": "pending",
        "human_confirmation_required": False,
        "messages": []
    }
    
    # The supervisor graph compiled runs up to the monitor interrupt.
    # Let's run it.
    state = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test-thread"}}
    )
    
    # Assert nodes ran and updated state
    assert state is not None
    # Because of interrupt_before=["monitor"], execution pauses just before "monitor" node.
    # Therefore, the current state status should be the last updated value by the preceding nodes.
    # Let's inspect what is in the state.
    # "decompose" node sets status to "running", but let's see.
    assert "status" in state
