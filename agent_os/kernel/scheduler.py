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
        Each task: {"id": 1, "dependencies": [], ...}
        execute_task_fn: async function that accepts a task dict and runs it.
        """
        # Map tasks by ID for easy lookup
        task_map = {t["id"]: t for t in tasks}
        
        # Build dependency adjacency
        dependencies_left: Dict[Any, Set[Any]] = {}
        dependents: Dict[Any, Set[Any]] = {t["id"]: set() for t in tasks}
        
        for t in tasks:
            deps = set(t.get("dependencies", []))
            # Filter out dependencies that are not in the task list
            deps = {d for d in deps if d in task_map}
            dependencies_left[t["id"]] = deps
            for d in deps:
                dependents[d].add(t["id"])
                
        # Status tracking
        completed: Set[Any] = set()
        failed: Set[Any] = set()
        running: Set[Any] = set()
        
        # Concurrency semaphore
        sem = asyncio.Semaphore(self.concurrency_limit)
        results: Dict[Any, Any] = {}
        
        # We use an event to yield when a task completes
        task_completed_event = asyncio.Event()
        
        async def run_task(task_id: Any) -> None:
            async with sem:
                task = task_map[task_id]
                try:
                    res = await execute_task_fn(task)
                    results[task_id] = {"status": "success", "result": res}
                    completed.add(task_id)
                except Exception as e:
                    results[task_id] = {"status": "failed", "error": str(e)}
                    failed.add(task_id)
                finally:
                    running.remove(task_id)
                    task_completed_event.set()
                    
        while len(completed) + len(failed) < len(tasks):
            # Find tasks that are ready to run
            ready_tasks = [
                tid for tid in task_map
                if tid not in running and tid not in completed and tid not in failed
                and all(dep in completed for dep in dependencies_left[tid])
            ]
            
            # If any dependency of a task failed, that task is also failed (cascade failure)
            cascading_failed = False
            for tid in list(task_map.keys()):
                if tid not in running and tid not in completed and tid not in failed:
                    if any(dep in failed for dep in dependencies_left[tid]):
                        failed.add(tid)
                        results[tid] = {"status": "skipped", "error": "Dependency failed"}
                        cascading_failed = True
                        
            if cascading_failed:
                continue
                
            if not ready_tasks and not running:
                # Deadlock/Cycle detected
                uncompleted = [tid for tid in task_map if tid not in completed and tid not in failed]
                for tid in uncompleted:
                    failed.add(tid)
                    results[tid] = {"status": "failed", "error": "Deadlock/Cycle detected"}
                break
                
            # Launch ready tasks
            for tid in ready_tasks:
                running.add(tid)
                asyncio.create_task(run_task(tid))
                
            # Wait for at least one running task to complete before checking again
            if running:
                task_completed_event.clear()
                await task_completed_event.wait()
                
        return results
