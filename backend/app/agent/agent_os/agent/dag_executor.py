"""
DAG (Directed Acyclic Graph) validation and execution.

Ensures:
  - No duplicate task IDs
  - No missing dependencies
  - No circular dependencies
  - Proper dependency ordering
  - Parallel execution of independent tasks
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .interfaces import Task


class DAGError(Exception):
    """DAG validation or execution error."""


@dataclass
class TaskDependency:
    """Task with its dependencies resolved."""
    task: Task
    dependencies: list[Task]
    dependents: list[Task]


class TaskGraphValidator:
    """Validates task graph for correctness."""

    @staticmethod
    def validate(tasks: list[Task]) -> tuple[bool, list[str]]:
        """
        Validate task graph.

        Checks:
          - No duplicate IDs
          - No missing dependencies
          - No self-dependencies
          - No circular dependencies
          - All tasks have allowed_paths defined

        Returns:
            (is_valid, list of errors)
        """
        errors = []

        if not tasks:
            return True, []

        # 1. Check for duplicate IDs
        seen_ids = set()
        for t in tasks:
            if t.task_id in seen_ids:
                errors.append(f"Duplicate task ID: {t.task_id}")
            seen_ids.add(t.task_id)

        # 2. Build ID map
        task_map = {t.task_id: t for t in tasks}

        # 3. Check for missing dependencies
        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id not in task_map:
                    errors.append(f"Task {task.task_id} depends on missing task {dep_id}")

        # 4. Check for self-dependencies
        for task in tasks:
            if task.task_id in task.depends_on:
                errors.append(f"Task {task.task_id} has self-dependency")

        # 5. Check for allowed_paths
        for task in tasks:
            is_valid_paths, path_errors = task.validate_paths()
            if not is_valid_paths:
                errors.extend(path_errors)

        # 6. Check for circular dependencies (if no other errors)
        if not errors:
            if not TaskGraphValidator._is_acyclic(task_map):
                errors.append("Task graph contains circular dependencies")

        return len(errors) == 0, errors

    @staticmethod
    def _is_acyclic(task_map: dict[str, Task]) -> bool:
        """Check if task graph is acyclic using DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = task_map[task_id]
            for dep_id in task.depends_on:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in task_map:
            if task_id not in visited:
                if has_cycle(task_id):
                    return False

        return True

    @staticmethod
    def topological_sort(tasks: list[Task]) -> list[Task]:
        """
        Return tasks in topological order.

        Tasks with no dependencies come first.
        """
        task_map = {t.task_id: t for t in tasks}
        in_degree = {t.task_id: len(t.depends_on) for t in tasks}

        # Find all tasks with in_degree 0
        queue = [t for t in tasks if in_degree[t.task_id] == 0]
        result = []

        while queue:
            task = queue.pop(0)
            result.append(task)

            # Find dependents (tasks that depend on this one)
            for other_task in tasks:
                if task.task_id in other_task.depends_on:
                    in_degree[other_task.task_id] -= 1
                    if in_degree[other_task.task_id] == 0:
                        queue.append(other_task)

        return result


class DAGExecutor:
    """Executes task DAG with proper dependency handling."""

    def __init__(self, max_concurrent: int = 4):
        """
        Initialize executor.

        Args:
            max_concurrent: Maximum concurrent task executions
        """
        self.max_concurrent = max_concurrent

    async def execute_graph(
        self,
        tasks: list[Task],
        execute_task_fn: Callable[[Task], Any],
        on_task_completed: Callable[[Task, Any], None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Execute task graph respecting dependencies.

        Args:
            tasks: List of tasks to execute
            execute_task_fn: Function that executes a single task, returns result
            on_task_completed: Optional callback when task completes

        Returns:
            Dict mapping task_id -> {"status": "success"/"failed"/"skipped", "result": ...}

        Raises:
            DAGError if graph is invalid
        """
        # 1. Validate graph
        is_valid, errors = TaskGraphValidator.validate(tasks)
        if not is_valid:
            raise DAGError(f"Invalid task graph: {'; '.join(errors)}")

        # 2. Build task map and dependency info
        task_map = {t.task_id: t for t in tasks}
        in_degree = {t.task_id: len(t.depends_on) for t in tasks}
        task_results: dict[str, dict[str, Any]] = {}

        # Track which tasks failed so we can skip dependents
        failed_tasks: set[str] = set()

        # 3. Execute with concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)
        lock = asyncio.Lock()
        ready_queue: list[Task] = [t for t in tasks if in_degree[t.task_id] == 0]
        running_tasks: set[asyncio.Task] = set()

        async def execute_with_semaphore(task: Task) -> None:
            """Execute a single task with semaphore."""
            async with semaphore:
                try:
                    # Skip if dependency failed or was skipped
                    parent_skipped_or_failed = any(
                        dep in failed_tasks or (dep in task_results and task_results[dep].get("status") == "skipped")
                        for dep in task.depends_on
                    )
                    if parent_skipped_or_failed:
                        async with lock:
                            task_results[task.task_id] = {
                                "status": "skipped",
                                "result": None,
                                "error": "Dependency failed or skipped",
                            }
                        return

                    # Execute task
                    result = await execute_task_fn(task)

                    # Store result
                    async with lock:
                        task_results[task.task_id] = result
                        if result.get("status") == "failed":
                            failed_tasks.add(task.task_id)

                    # Callback
                    if on_task_completed:
                        on_task_completed(task, result)

                except Exception as e:
                    async with lock:
                        task_results[task.task_id] = {
                            "status": "failed",
                            "result": None,
                            "error": str(e),
                        }
                        failed_tasks.add(task.task_id)

        # 4. Main execution loop
        while ready_queue or running_tasks:
            # Start new tasks if semaphore allows
            while ready_queue and len(running_tasks) < self.max_concurrent:
                task = ready_queue.pop(0)
                task_obj = asyncio.create_task(execute_with_semaphore(task))
                running_tasks.add(task_obj)

            # Wait for at least one task to complete
            if running_tasks:
                done, running_tasks = await asyncio.wait(
                    running_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Process completed task to update dependencies
                async with lock:
                    for task_id, task_obj in task_map.items():
                        # Check if this task's dependencies are all complete
                        if task_id not in task_results:
                            all_deps_done = all(
                                dep_id in task_results for dep_id in task_obj.depends_on
                            )
                            if all_deps_done:
                                ready_queue.append(task_obj)

            # Check for deadlock
            if not ready_queue and running_tasks:
                # Wait a bit more
                await asyncio.sleep(0.1)
            elif not ready_queue and not running_tasks:
                # All done
                break

        return task_results

    def get_execution_order(self, tasks: list[Task]) -> list[str]:
        """Get topologically sorted task IDs."""
        sorted_tasks = TaskGraphValidator.topological_sort(tasks)
        return [t.task_id for t in sorted_tasks]
