"""
DAG Validator — Validates task graphs before execution.

Catches duplicate IDs, missing dependencies, cycles, and schema errors
BEFORE the scheduler starts running tasks, rather than detecting problems
after they cause failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("agent_runtime.orchestration.validator")


class TaskGraphError(Exception):
    """Base exception for task graph validation failures."""


class DuplicateTaskIdError(TaskGraphError):
    """Raised when two tasks share the same ID."""


class MissingDependencyError(TaskGraphError):
    """Raised when a task depends on a non-existent task."""


class CyclicDependencyError(TaskGraphError):
    """Raised when the task graph contains a cycle."""


class InvalidTaskSchemaError(TaskGraphError):
    """Raised when a task dict is missing required fields."""


@dataclass
class ValidationResult:
    """Result of validating a task graph."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    task_count: int = 0
    edge_count: int = 0


class TaskGraphValidator:
    """Validates a task graph (list of task dicts) for correctness.

    Checks performed:
    1. Required fields present (id, depends_on)
    2. No duplicate task IDs
    3. No self-dependencies
    4. All dependencies reference existing tasks
    5. No cycles (topological sort)
    """

    REQUIRED_FIELDS = {"id"}

    def validate(self, tasks: list[dict[str, Any]]) -> ValidationResult:
        """Validate a task graph and return structured results.

        Args:
            tasks: List of task dicts, each with at least "id" and optionally "depends_on".

        Returns:
            ValidationResult indicating whether the graph is valid.

        Raises:
            TaskGraphError subclasses if validation fails.
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not tasks:
            return ValidationResult(valid=True, task_count=0, edge_count=0)

        # 1. Check required fields
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                errors.append(f"Task at index {i} is not a dict: {type(task)}")
                continue
            for field_name in self.REQUIRED_FIELDS:
                if field_name not in task:
                    errors.append(f"Task at index {i} missing required field '{field_name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, task_count=len(tasks))

        # 2. Check for duplicate IDs
        seen_ids: dict[str, int] = {}
        for i, task in enumerate(tasks):
            tid = task["id"]
            if tid in seen_ids:
                errors.append(
                    f"Duplicate task ID '{tid}' at indices {seen_ids[tid]} and {i}"
                )
            else:
                seen_ids[tid] = i

        if errors:
            return ValidationResult(valid=False, errors=errors, task_count=len(tasks))

        all_ids = set(seen_ids.keys())
        total_edges = 0

        # 3. Check self-dependencies and missing dependencies
        for task in tasks:
            tid = task["id"]
            deps = task.get("depends_on", [])

            if not isinstance(deps, list):
                errors.append(f"Task '{tid}': depends_on must be a list, got {type(deps)}")
                continue

            total_edges += len(deps)

            for dep in deps:
                if dep == tid:
                    errors.append(f"Task '{tid}' has a self-dependency")
                elif dep not in all_ids:
                    errors.append(
                        f"Task '{tid}' depends on unknown task '{dep}'. "
                        f"Known IDs: {sorted(all_ids)}"
                    )

        if errors:
            return ValidationResult(
                valid=False,
                errors=errors,
                task_count=len(tasks),
                edge_count=total_edges,
            )

        # 4. Cycle detection via topological sort (Kahn's algorithm)
        in_degree = {task["id"]: 0 for task in tasks}
        adjacency: dict[str, list[str]] = {task["id"]: [] for task in tasks}

        for task in tasks:
            tid = task["id"]
            for dep in task.get("depends_on", []):
                adjacency[dep].append(tid)
                in_degree[tid] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        sorted_count = 0

        while queue:
            node = queue.pop(0)
            sorted_count += 1
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if sorted_count != len(tasks):
            # Find the cycle participants
            cycle_tasks = [tid for tid, deg in in_degree.items() if deg > 0]
            errors.append(
                f"Cyclic dependency detected involving tasks: {cycle_tasks}"
            )
            return ValidationResult(
                valid=False,
                errors=errors,
                task_count=len(tasks),
                edge_count=total_edges,
            )

        # 5. Warnings for common issues
        orphan_tasks = [
            task["id"] for task in tasks
            if not task.get("depends_on") and not any(
                task["id"] in t.get("depends_on", []) for t in tasks
            )
        ]
        if len(orphan_tasks) > 1:
            warnings.append(
                f"Multiple root tasks with no connections: {orphan_tasks}. "
                "Consider if they should have dependencies."
            )

        return ValidationResult(
            valid=True,
            errors=[],
            warnings=warnings,
            task_count=len(tasks),
            edge_count=total_edges,
        )

    def validate_or_raise(self, tasks: list[dict[str, Any]]) -> None:
        """Validate and raise on first error.

        Convenience method for use in pipelines where validation
        failure should immediately stop execution.
        """
        result = self.validate(tasks)
        if not result.valid:
            error_msg = "; ".join(result.errors)
            # Pick the most specific exception type
            for err in result.errors:
                if "Duplicate" in err:
                    raise DuplicateTaskIdError(error_msg)
                if "unknown task" in err:
                    raise MissingDependencyError(error_msg)
                if "Cyclic" in err:
                    raise CyclicDependencyError(error_msg)
                if "self-dependency" in err:
                    raise CyclicDependencyError(error_msg)
            raise TaskGraphError(error_msg)
