import asyncio
from typing import Any, Dict, List, Set, Callable, Coroutine


class DependencyScheduler:
    """Schedules and runs tasks concurrently respecting their dependency graph."""
    def __init__(self, concurrency_limit: int = 4) -> None:
        self.concurrency_limit = concurrency_limit

    async def execute_graph(
        self,
        tasks: List[Dict[str, Any]],
        execute_task_fn: Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]
    ) -> Dict[str, Any]:
        """
        Executes a list of task dicts.
        Each task: {"id": 1, "dependencies": [], "priority": 0, ...}
        execute_task_fn: async function that accepts a task dict and runs it.
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
                
        completed: Set[Any] = set()
        failed: Set[Any] = set()
        running: Set[Any] = set()
        results: Dict[Any, Any] = {}
        
        # Priority-sorted ready queue: lower priority number runs first
        ready_queue = [tid for tid, deg in in_degree.items() if deg == 0]
        ready_queue.sort(key=lambda tid: task_map[tid].get("priority", 0))
        
        task_completed_event = asyncio.Event()

        def cascade_failure(failed_id: Any) -> None:
            queue = list(dependents[failed_id])
            visited = set(queue)
            while queue:
                curr = queue.pop(0)
                if curr not in completed and curr not in failed and curr not in running:
                    failed.add(curr)
                    results[curr] = {"status": "skipped", "error": "Dependency failed"}
                    for dep in dependents[curr]:
                        if dep not in visited:
                            visited.add(dep)
                            queue.append(dep)

        async def run_task(task_id: Any) -> None:
            try:
                task = task_map[task_id]
                res = await execute_task_fn(task)
                results[task_id] = {"status": "success", "result": res}
                completed.add(task_id)
                
                # Unblock dependents
                for dep in dependents[task_id]:
                    if dep not in completed and dep not in failed:
                        in_degree[dep] -= 1
                        if in_degree[dep] == 0:
                            ready_queue.append(dep)
                # Re-sort ready queue by priority
                ready_queue.sort(key=lambda tid: task_map[tid].get("priority", 0))
            except Exception as e:
                results[task_id] = {"status": "failed", "error": str(e)}
                failed.add(task_id)
                cascade_failure(task_id)
            finally:
                if task_id in running:
                    running.remove(task_id)
                task_completed_event.set()

        while len(completed) + len(failed) < len(tasks):
            # Dispatch as many ready tasks as concurrency limit allows
            while len(running) < self.concurrency_limit and ready_queue:
                next_id = ready_queue.pop(0)
                running.add(next_id)
                asyncio.create_task(run_task(next_id))
                
            if not running and not ready_queue:
                # Cycle or Deadlock detected
                uncompleted = [tid for tid in task_map if tid not in completed and tid not in failed]
                for tid in uncompleted:
                    failed.add(tid)
                    results[tid] = {"status": "failed", "error": "Deadlock/Cycle detected"}
                break
                
            task_completed_event.clear()
            await task_completed_event.wait()
            
        return results

