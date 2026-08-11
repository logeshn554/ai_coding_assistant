"""
Tests for DAG validation and execution (Phase 3a).
"""

import pytest
import asyncio

from agent_os.agent import Task, DAGError
from agent_os.agent.dag_executor import TaskGraphValidator, DAGExecutor


class TestTaskGraphValidator:
    """Test DAG validation."""

    def test_valid_simple_dag(self):
        """Test validation of simple DAG."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t2",
                title="Second",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],
            ),
        ]

        is_valid, errors = TaskGraphValidator.validate(tasks)
        assert is_valid
        assert len(errors) == 0

    def test_duplicate_task_ids(self):
        """Test detection of duplicate task IDs."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t1",
                title="Duplicate",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
        ]

        is_valid, errors = TaskGraphValidator.validate(tasks)
        assert not is_valid
        assert any("Duplicate" in e for e in errors)

    def test_missing_dependency(self):
        """Test detection of missing dependency."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t_missing"],  # Missing!
            ),
        ]

        is_valid, errors = TaskGraphValidator.validate(tasks)
        assert not is_valid
        assert any("missing" in e.lower() for e in errors)

    def test_self_dependency(self):
        """Test detection of self-dependency."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],  # Self!
            ),
        ]

        is_valid, errors = TaskGraphValidator.validate(tasks)
        assert not is_valid
        assert any("self-dependency" in e.lower() for e in errors)

    def test_circular_dependency(self):
        """Test detection of circular dependency."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t2"],
            ),
            Task(
                task_id="t2",
                title="Second",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],  # Circular!
            ),
        ]

        is_valid, errors = TaskGraphValidator.validate(tasks)
        assert not is_valid
        assert any("circular" in e.lower() for e in errors)

    def test_no_allowed_paths(self):
        """Test detection of missing allowed_paths."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=[],  # Empty!
            ),
        ]

        is_valid, errors = TaskGraphValidator.validate(tasks)
        assert not is_valid

    def test_topological_sort(self):
        """Test topological sorting."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t3",
                title="Third",
                description="Task 3",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1", "t2"],
            ),
            Task(
                task_id="t2",
                title="Second",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],
            ),
        ]

        sorted_tasks = TaskGraphValidator.topological_sort(tasks)
        task_ids = [t.task_id for t in sorted_tasks]

        # t1 should come first
        assert task_ids.index("t1") == 0
        # t2 should come after t1
        assert task_ids.index("t1") < task_ids.index("t2")
        # t3 should come after both t1 and t2
        assert task_ids.index("t2") < task_ids.index("t3")


class TestDAGExecutor:
    """Test DAG execution."""

    @pytest.mark.asyncio
    async def test_simple_sequential_execution(self):
        """Test executing a simple sequential DAG."""
        execution_order = []

        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t2",
                title="Second",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],
            ),
        ]

        async def execute_task(task: Task):
            execution_order.append(task.task_id)
            await asyncio.sleep(0.01)
            return {"status": "success", "result": f"Task {task.task_id} complete"}

        executor = DAGExecutor()
        results = await executor.execute_graph(tasks, execute_task)

        # Check results
        assert results["t1"]["status"] == "success"
        assert results["t2"]["status"] == "success"

        # Check execution order
        assert execution_order.index("t1") < execution_order.index("t2")

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test executing independent tasks in parallel."""
        execution_order = []
        concurrent_count = 0
        max_concurrent = 0

        tasks = [
            Task(
                task_id="t1",
                title="Task 1",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t2",
                title="Task 2",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t3",
                title="Task 3",
                description="Task 3",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1", "t2"],
            ),
        ]

        lock = asyncio.Lock()

        async def execute_task(task: Task):
            nonlocal concurrent_count, max_concurrent
            execution_order.append(task.task_id)

            async with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)

            await asyncio.sleep(0.05)

            async with lock:
                concurrent_count -= 1

            return {"status": "success", "result": None}

        executor = DAGExecutor(max_concurrent=2)
        results = await executor.execute_graph(tasks, execute_task)

        # Check results
        assert all(r["status"] == "success" for r in results.values())

        # t1 and t2 should execute before t3
        t1_idx = execution_order.index("t1")
        t2_idx = execution_order.index("t2")
        t3_idx = execution_order.index("t3")

        assert t1_idx < t3_idx
        assert t2_idx < t3_idx

    @pytest.mark.asyncio
    async def test_task_failure_skips_dependents(self):
        """Test that task failure causes dependents to be skipped."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t2",
                title="Second",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],
            ),
            Task(
                task_id="t3",
                title="Third",
                description="Task 3",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t2"],
            ),
        ]

        async def execute_task(task: Task):
            if task.task_id == "t1":
                return {"status": "failed", "result": None, "error": "Intentional failure"}
            return {"status": "success", "result": None}

        executor = DAGExecutor()
        results = await executor.execute_graph(tasks, execute_task)

        # t1 fails
        assert results["t1"]["status"] == "failed"

        # t2 and t3 should be skipped
        assert results["t2"]["status"] == "skipped"
        assert results["t3"]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_invalid_dag_raises_error(self):
        """Test that invalid DAG raises error."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t_missing"],  # Invalid!
            ),
        ]

        async def execute_task(task: Task):
            return {"status": "success", "result": None}

        executor = DAGExecutor()

        with pytest.raises(DAGError):
            await executor.execute_graph(tasks, execute_task)

    @pytest.mark.asyncio
    async def test_get_execution_order(self):
        """Test getting topological execution order."""
        tasks = [
            Task(
                task_id="t1",
                title="First",
                description="Task 1",
                agent_type="coding",
                allowed_paths=["/workspace"],
            ),
            Task(
                task_id="t3",
                title="Third",
                description="Task 3",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1", "t2"],
            ),
            Task(
                task_id="t2",
                title="Second",
                description="Task 2",
                agent_type="coding",
                allowed_paths=["/workspace"],
                depends_on=["t1"],
            ),
        ]

        executor = DAGExecutor()
        order = executor.get_execution_order(tasks)

        assert order == ["t1", "t2", "t3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
