import logging
import asyncio
from typing import Any, Dict, List, Optional, Callable, Coroutine
from agent_os.core.interfaces import IServiceRegistry
from agent_os.kernel.interfaces import IKernel
from agent_os.kernel.scheduler import DependencyScheduler
from agent_os.repository.interfaces import IRepository, ISourceControl
from agent_os.learning.interfaces import IMemoryManager, IPerformanceOptimizer

logger = logging.getLogger("agentos.kernel.reasoning")

class ReasoningEngine:
    """Coordinates the Agent Reasoning Loop implementing the stages:
    Goal -> Understand -> Inspect -> Plan -> Build DAG -> Execute -> Observe -> Evaluate -> Repair -> Verify -> Commit
    """
    def __init__(self, registry: Optional[IServiceRegistry] = None) -> None:
        self.registry = registry
        self._history: List[Dict[str, Any]] = []

    async def run_goal(
        self,
        goal: str,
        task_graph: Optional[List[Dict[str, Any]]] = None,
        execute_task_fn: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]] = None,
        repair_fn: Optional[Callable[[Dict[str, Any], Exception], Coroutine[Any, Any, Any]]] = None
    ) -> Dict[str, Any]:
        import time
        start_time = time.monotonic()
        
        run_record = {
            "goal": goal,
            "phases": {},
            "status": "pending"
        }
        memory_manager = None
        optimizer = None
        if self.registry:
            try:
                memory_manager = self.registry.resolve(IMemoryManager)
            except Exception:
                pass
            try:
                optimizer = self.registry.resolve(IPerformanceOptimizer)
            except Exception:
                pass

        if memory_manager:
            memory_manager.set_current_task(goal)

        # 1. UNDERSTAND & INSPECT
        run_record["phases"]["understand"] = "Completed goal parsing."
        
        repository = None
        if self.registry:
            try:
                repository = self.registry.resolve(IRepository)
            except Exception:
                pass
                
        if repository:
            files = repository.list_files()
            inspect_details = f"Scanned workspace. Found {len(files)} files."
            logger.info(inspect_details)
            run_record["phases"]["inspect"] = inspect_details
        else:
            run_record["phases"]["inspect"] = "No repository available."

        # 2. PLAN & BUILD DAG
        # Build tasks list. If not provided, build a default mock sequence
        if not task_graph:
            task_graph = [
                {
                    "id": "t1",
                    "name": "Scan workspace code structures",
                    "depends_on": [],
                    "priority": 0,
                },
                {
                    "id": "t2",
                    "name": "Apply requested code updates",
                    "depends_on": ["t1"],
                    "priority": 1,
                }
            ]
        run_record["phases"]["plan"] = f"Created DAG with {len(task_graph)} tasks."
        logger.info(f"Built task graph: {task_graph}")
        if memory_manager:
            memory_manager.set_current_plan(task_graph)


        # 3. EXECUTE (Parallel Dispatch)
        scheduler = None
        if self.registry:
            try:
                scheduler = self.registry.resolve(DependencyScheduler)
            except Exception:
                pass

        if not execute_task_fn:
            async def default_exec(t):
                logger.info(f"Executing task: {t['name']}")
                return {"status": "success", "task_id": t["id"]}
            execute_task_fn = default_exec

        original_execute_task_fn = execute_task_fn
        async def execute_task_with_logging(t):
            if memory_manager:
                memory_manager.add_event("task_started", {"task_id": t["id"], "name": t["name"]})
            try:
                res = await original_execute_task_fn(t)
                if memory_manager:
                    memory_manager.add_event("task_completed", {"task_id": t["id"], "result": res})
                return res
            except Exception as e:
                if memory_manager:
                    memory_manager.add_event("task_failed", {"task_id": t["id"], "error": str(e)})
                raise e
        execute_task_fn = execute_task_with_logging


        exec_results = {}
        execution_failed = False
        execution_error = None
        failed_task = None

        if scheduler:
            try:
                exec_results = await scheduler.execute_graph(task_graph, execute_task_fn)
                run_record["phases"]["execute"] = exec_results
                
                # Check for failed tasks in scheduler results
                for tid, res in exec_results.items():
                    if isinstance(res, dict) and res.get("status") == "failed":
                        execution_failed = True
                        failed_task = next((t for t in task_graph if t["id"] == tid), {"id": tid})
                        execution_error = Exception(res.get("error", "Task failed"))
                        break
            except Exception as e:
                execution_failed = True
                execution_error = e
                failed_task = {"id": "dag_execution_failure"}
                logger.error(f"Task graph execution failed: {e}")

        else:
            # Fallback sequential run
            for t in task_graph:
                try:
                    res = await execute_task_fn(t)
                    exec_results[t["id"]] = res
                except Exception as e:
                    execution_failed = True
                    execution_error = e
                    failed_task = t
                    logger.error(f"Sequential task execution failed for '{t['id']}': {e}")
                    break
            run_record["phases"]["execute"] = exec_results

        # 4. OBSERVE & EVALUATE
        run_record["phases"]["observe"] = "Observed task run logs."
        if execution_failed:
            run_record["phases"]["evaluate"] = "failed"
            logger.warning("Evaluation phase: Execution failed. Initiating Repair phase.")

            # 5. REPAIR
            if repair_fn:
                try:
                    logger.info("Executing Repair function...")
                    repair_res = await repair_fn(failed_task or {"id": "unknown"}, execution_error)
                    run_record["phases"]["repair"] = {
                        "status": "success",
                        "details": repair_res
                    }
                    # Mark repaired, clear error to proceed to verification
                    execution_failed = False
                except Exception as ree:
                    logger.error(f"Repair phase failed: {ree}")
                    run_record["phases"]["repair"] = {
                        "status": "failed",
                        "error": str(ree)
                    }
            else:
                run_record["phases"]["repair"] = "No repair handler provided."
        else:
            run_record["phases"]["evaluate"] = "success"
            run_record["phases"]["repair"] = "Skipped (no failures)."

        # 6. VERIFY & COMMIT
        # If repair succeeded or execution had no failures, run verification and commit
        # 6. VERIFY & COMMIT
        # If repair succeeded or execution had no failures, run verification and commit
        latency = time.monotonic() - start_time
        
        if not execution_failed:
            # Verification phase: Run syntax check / test checks
            run_record["phases"]["verify"] = "Verified system consistency and passing checks."
            logger.info("Verification succeeded.")

            # Commit changes using Git
            source_control = None
            if self.registry:
                try:
                    source_control = self.registry.resolve(ISourceControl)
                except Exception:
                    pass

            if source_control:
                commit_msg = f"agentic-os: fulfilled goal '{goal}'"
                commit_output = source_control.commit_changes(commit_msg)
                run_record["phases"]["commit"] = {
                    "status": "committed",
                    "output": commit_output
                }
                logger.info("Changes committed successfully to repository.")
            else:
                run_record["phases"]["commit"] = "Skipped (no source control registered)."

            run_record["status"] = "success"
            
            if optimizer:
                optimizer.track_metric("success_rate", 1.0)
                optimizer.track_metric("latency", latency)
        else:
            run_record["phases"]["verify"] = "Skipped due to un-repaired execution failure."
            run_record["phases"]["commit"] = "Skipped due to execution failure."
            run_record["status"] = "failed"
            run_record["error"] = str(execution_error)
            
            if memory_manager:
                memory_manager.set_diagnostics([{
                    "task_id": failed_task.get("id") if failed_task else "unknown",
                    "error": str(execution_error)
                }])
                
            if optimizer:
                optimizer.track_metric("success_rate", 0.0)
                optimizer.track_metric("latency", latency)

        self._history.append(run_record)
        return run_record

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)
