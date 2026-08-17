"""
Priority Scheduler — Priority queue with dependency-aware task scheduling.
"""
from __future__ import annotations

import logging

from .dag_generator import DagTask

logger = logging.getLogger("loopix.work_graph.priority_scheduler")


class PriorityScheduler:
    """Schedules tasks from a dependency DAG, queuing ready tasks in priority order."""

    def __init__(self) -> None:
        self._tasks: dict[str, DagTask] = {}

    def load_dag(self, tasks: list[DagTask]) -> None:
        self._tasks = {t.task_id: t for t in tasks}

    def get_ready_tasks(self) -> list[DagTask]:
        """Find all pending tasks whose dependencies are successfully completed."""
        ready = []
        for task in self._tasks.values():
            if task.status != "pending":
                continue

            deps_satisfied = True
            for dep_id in task.dependencies:
                dep = self._tasks.get(dep_id)
                if not dep or dep.status != "success":
                    deps_satisfied = False
                    break

            if deps_satisfied:
                ready.append(task)

        return ready

    def mark_success(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = "success"
            logger.debug(f"Task marked as SUCCESS in scheduler: {task_id}")

    def mark_failure(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = "failed"
            logger.debug(f"Task marked as FAILED in scheduler: {task_id}")

    def get_all_tasks(self) -> list[DagTask]:
        return list(self._tasks.values())


# ── Singleton ───────────────────────────────────────────────────────────────

priority_scheduler = PriorityScheduler()
