import pytest
from parallel_agent_system.core.state import SubTask, AgentResult, GraphState
from parallel_agent_system.graph.nodes.decompose import decompose_task_node
from parallel_agent_system.graph.nodes.router import _dependencies_met, run_agents_parallel_node


@pytest.mark.asyncio
async def test_decompose_task_node():
    """Verify that decompose_task_node converts a goal into distinct SubTasks with resolved dependencies."""
    initial_state = {
        "goal": "Write code for a feature, then add unit tests, and do a security review.",
        "subtasks": [],
        "results": [],
        "global_cost_usd": 0.0,
        "iteration": 0,
        "status": "pending",
        "human_confirmation_required": False,
        "messages": []
    }

    result = await decompose_task_node(initial_state)
    assert "subtasks" in result
    assert result["status"] == "running"
    
    subtasks = result["subtasks"]
    assert len(subtasks) == 3
    
    # Verify we resolved string description dependencies to task UUIDs
    code_task = next(t for t in subtasks if t.agent_type == "code")
    test_task = next(t for t in subtasks if t.agent_type == "test")
    review_task = next(t for t in subtasks if t.agent_type == "review")

    # Code task should have no dependencies
    assert code_task.depends_on == []
    # Test task should depend on Code task ID
    assert test_task.depends_on == [code_task.id]
    # Review task should depend on both Code and Test task IDs
    assert set(review_task.depends_on) == {code_task.id, test_task.id}


def test_dependencies_met():
    """Verify dependency tracking for subtasks."""
    t_code = SubTask(id="c1", agent_type="code", description="Code", workspace_dir="w")
    t_test = SubTask(id="t1", agent_type="test", description="Test", workspace_dir="w", depends_on=["c1"])
    t_review = SubTask(id="r1", agent_type="review", description="Review", workspace_dir="w", depends_on=["c1", "t1"])

    results = []
    
    # 1. Initially, only code task has dependencies met (none)
    assert _dependencies_met(t_code, results) is True
    assert _dependencies_met(t_test, results) is False
    assert _dependencies_met(t_review, results) is False

    # 2. Once code succeeds, test dependencies are met
    results.append(AgentResult(subtask_id="c1", agent_type="code", status="success", output="done", event_log_key="k"))
    assert _dependencies_met(t_test, results) is True
    assert _dependencies_met(t_review, results) is False

    # 3. If test fails, review dependencies are not met (since all must succeed)
    results.append(AgentResult(subtask_id="t1", agent_type="test", status="failed", output="err", event_log_key="k"))
    assert _dependencies_met(t_review, results) is False

    # 4. If test is replaced by success, review is met
    results[-1] = AgentResult(subtask_id="t1", agent_type="test", status="success", output="done", event_log_key="k")
    assert _dependencies_met(t_review, results) is True


@pytest.mark.asyncio
async def test_run_agents_parallel_node_batching():
    """Verify that run_agents_parallel_node executes tasks in dependent stages."""
    # Define tasks: Code -> Test -> Review
    t_code = SubTask(id="c1", agent_type="code", description="Code", workspace_dir="w")
    t_test = SubTask(id="t1", agent_type="test", description="Test", workspace_dir="w", depends_on=["c1"])
    t_review = SubTask(id="r1", agent_type="review", description="Review", workspace_dir="w", depends_on=["c1", "t1"])

    state = {
        "run_id": "r-1",
        "goal": "Build it",
        "subtasks": [t_code, t_test, t_review],
        "results": [],
        "global_cost_usd": 0.0,
        "iteration": 0,
        "status": "pending",
        "human_confirmation_required": False,
        "messages": []
    }

    # Run execution
    execution_result = await run_agents_parallel_node(state)
    assert "results" in execution_result
    results = execution_result["results"]
    
    # All 3 subtasks should run and complete successfully because they unblocked each other stage by stage
    assert len(results) == 3
    assert {r.subtask_id for r in results} == {"c1", "t1", "r1"}
    
    # Confirm status values
    for r in results:
        assert r.status == "success"
