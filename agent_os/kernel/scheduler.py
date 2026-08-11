import asyncio
import logging
from typing import Any, Dict, List, Set, Callable, Coroutine

logger = logging.getLogger("agentos.kernel.scheduler")


class DependencyScheduler:
    """Schedules and runs tasks concurrently respecting their dependency graph.

    All shared mutable state (ready_queue, running, completed, failed, in_degree,
    results) is protected by an asyncio.Lock to prevent race conditions when
    concurrent fire-and-forget tasks modify them simultaneously.

    An asyncio.Semaphore enforces the concurrency limit so at most N tasks
    execute their payloads in parallel.
    """
    def __init__(self, concurrency_limit: int = 4) -> None:
        self.concurrency_limit = concurrency_limit

    async def execute_graph(
        self,
        tasks: List[Dict[str, Any]],
        execute_task_fn: Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]
    ) -> Dict[str, Any]:
        """
        Executes a list of task dicts respecting their DAG dependencies.
        Each task: {"id": 1, "dependencies": [], "priority": 0, ...}
        execute_task_fn: async function that accepts a task dict and runs it.

        Returns a dict mapping task_id → {"status": ..., "result"|"error": ...}.
        """
        if not tasks:
            return {}

        task_map = {t["id"]: t for t in tasks}

        # Build dependency structures
        in_degree: Dict[Any, int] = {}
        dependents: Dict[Any, Set[Any]] = {t["id"]: set() for t in tasks}

        for t in tasks:
            tid = t["id"]
            deps = set(t.get("dependencies", []))
            # Filter out dependencies not in the task list
            deps = {d for d in deps if d in task_map}
            in_degree[tid] = len(deps)
            for d in deps:
                dependents[d].add(tid)

        # ── Synchronized shared state ──
        state_lock = asyncio.Lock()
        concurrency_sem = asyncio.Semaphore(self.concurrency_limit)

        completed: Set[Any] = set()
        failed: Set[Any] = set()
        running: Set[Any] = set()
        results: Dict[Any, Any] = {}

        # Priority-sorted ready queue: lower priority number runs first
        ready_queue: List[Any] = sorted(
            [tid for tid, deg in in_degree.items() if deg == 0],
            key=lambda tid: task_map[tid].get("priority", 0),
        )

        # Signalled whenever a task finishes so the dispatcher can re-check
        task_completed_event = asyncio.Event()

        # Keep references so we can await everything at the end
        spawned_tasks: List[asyncio.Task] = []

        def _cascade_failure_locked(failed_id: Any) -> None:
            """Mark all transitive dependents of *failed_id* as skipped.

            MUST be called while state_lock is held.
            """
            queue = list(dependents.get(failed_id, set()))
            visited = set(queue)
            while queue:
                curr = queue.pop(0)
                if curr not in completed and curr not in failed and curr not in running:
                    failed.add(curr)
                    results[curr] = {"status": "skipped", "error": "Dependency failed"}
                    for dep in dependents.get(curr, set()):
                        if dep not in visited:
                            visited.add(dep)
                            queue.append(dep)

        async def run_task(task_id: Any) -> None:
            """Execute a single task, then update shared state under the lock."""
            try:
                task = task_map[task_id]
                async with concurrency_sem:
                    res = await execute_task_fn(task)

                # ── Success path: update state under lock ──
                async with state_lock:
                    results[task_id] = {"status": "success", "result": res}
                    completed.add(task_id)
                    running.discard(task_id)

                    # Unblock dependents
                    for dep in dependents.get(task_id, set()):
                        if dep not in completed and dep not in failed:
                            in_degree[dep] -= 1
                            if in_degree[dep] == 0:
                                ready_queue.append(dep)
                    # Re-sort ready queue by priority
                    ready_queue.sort(key=lambda tid: task_map[tid].get("priority", 0))

                    task_completed_event.set()

            except Exception as e:
                logger.error(f"Task '{task_id}' failed: {e}")
                async with state_lock:
                    results[task_id] = {"status": "failed", "error": str(e)}
                    failed.add(task_id)
                    running.discard(task_id)
                    _cascade_failure_locked(task_id)
                    task_completed_event.set()

        # ── Main dispatch loop ──
        while True:
            async with state_lock:
                # Termination check
                if len(completed) + len(failed) >= len(tasks):
                    break

                # Dispatch as many ready tasks as possible
                dispatched_any = False
                while ready_queue:
                    next_id = ready_queue.pop(0)
                    if next_id in completed or next_id in failed:
                        continue  # stale entry
                    running.add(next_id)
                    t = asyncio.create_task(run_task(next_id))
                    spawned_tasks.append(t)
                    dispatched_any = True

                if not running and not ready_queue:
                    # Deadlock / cycle: mark all remaining as failed
                    uncompleted = [
                        tid for tid in task_map
                        if tid not in completed and tid not in failed
                    ]
                    for tid in uncompleted:
                        failed.add(tid)
                        results[tid] = {"status": "failed", "error": "Deadlock/Cycle detected"}
                    break

            # Wait for at least one task to finish before re-checking
            task_completed_event.clear()
            await task_completed_event.wait()

        # Await any still-running tasks (should be done, but ensures cleanup)
        if spawned_tasks:
            await asyncio.gather(*spawned_tasks, return_exceptions=True)

        return results

