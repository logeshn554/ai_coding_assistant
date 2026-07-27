import asyncio
from typing import Any

from parallel_agent_system.core.state import SubTask, AgentResult, GraphState
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.monitor.stuck_detector import StuckDetector


# --- Dependency Resolution Helper ---

def _dependencies_met(subtask: SubTask, results: list[AgentResult]) -> bool:
    """
    Checks if all dependencies for a subtask have completed successfully.
    """
    successful_ids = {r.subtask_id for r in results if r.status == "success"}
    return all(dep_id in successful_ids for dep_id in subtask.depends_on)


# --- Router Nodes ---

async def route_node(state: GraphState) -> dict:
    """
    Routing node that forwards execution to agent node.
    """
    return {"status": "running"}


async def run_agents_parallel_node(state: GraphState) -> dict:
    """
    Executes independent subtasks concurrently in parallel batches using asyncio.gather.
    Resolves dependencies iteratively in multiple passes until no more tasks can progress.
    """
    config = SystemConfig()
    
    # Track accumulated results in this step (reducer accumulates them to state["results"] at the end)
    current_results: list[AgentResult] = list(state.get("results", []))
    new_results: list[AgentResult] = []

    # Get a list of subtasks that are not yet executed
    subtasks = state.get("subtasks", [])

    # Registry of agents (imported dynamically or mocked)
    agent_registry = {}
    try:
        from parallel_agent_system.agents import AGENT_REGISTRY
        agent_registry = AGENT_REGISTRY
    except ImportError:
        pass

    session = state.get("session")
    run_id = state.get("run_id", "")
    attempt = state.get("iteration", 1)

    # Ensure run_id and attempt are populated in subtask models
    for t in subtasks:
        t.run_id = run_id
        t.attempt = attempt

    async def run_one(subtask: SubTask) -> AgentResult:
        """Executes a single subtask, falling back to a mock result if the registry is missing."""
        if subtask.agent_type in agent_registry:
            agent_cls = agent_registry[subtask.agent_type]
            agent_instance = agent_cls(config=config)
            return await agent_instance.run(subtask, session=session)
        else:
            # Fallback mock runner for Phase 2 testing
            await asyncio.sleep(0.01)
            return AgentResult(
                subtask_id=subtask.id,
                agent_type=subtask.agent_type,
                status="success",
                output=f"Executed mock agent for task: {subtask.description}",
                files_changed=["src/main.py"] if subtask.agent_type == "code" else [],
                cost_usd=0.05,
                iterations=1,
                event_log_key=f"events:mock:{subtask.id}"
            )

    stuck_detector = StuckDetector(config=config)

    # Dependency resolution loop
    while True:
        # Identify subtasks that are not completed and have all dependencies met
        completed_ids = {r.subtask_id for r in current_results}
        pending_batch = [
            t for t in subtasks
            if t.id not in completed_ids and _dependencies_met(t, current_results)
        ]

        # If no more tasks can be run, break
        if not pending_batch:
            break

        # Execute the entire pending batch concurrently
        batch_results = list(await asyncio.gather(
            *[run_one(t) for t in pending_batch],
            return_exceptions=False
        ))

        # Check for stuck tasks and recurring errors using StuckDetector
        threshold = 2
        fallback_enabled = False
        try:
            from backend.app.state import config_manager
            threshold = config_manager.get_repeat_error_threshold()
            fallback_enabled = config_manager.get_web_search_fallback_enabled()
        except Exception:
            pass

        check_res = stuck_detector.check_detailed(subtasks, batch_results, repeat_error_threshold=threshold)
        stuck_task_ids = check_res.get("stuck_ids", [])
        web_search_task_ids = check_res.get("web_search_task_ids", [])
        error_signatures = check_res.get("error_signatures", {})

        if stuck_task_ids:
            for r in batch_results:
                if r.subtask_id in stuck_task_ids:
                    r.status = "stuck"

        # Web Search Fallback Trigger
        if fallback_enabled and web_search_task_ids:
            try:
                from backend.app.tools.web_search_tool import search_web
                for st_id in web_search_task_ids:
                    err_sig = error_signatures.get(st_id, "recurring error")
                    # Perform web search query
                    search_results = await search_web(err_sig, max_results=3)
                    if search_results:
                        formatted_search = "\n\n## Web search results for this recurring error\n" + "\n\n".join(
                            [f"### {sr.title}\nURL: {sr.url}\n{sr.snippet}" for sr in search_results]
                        )
                        # Append search results to corresponding subtask description for retry
                        for t in subtasks:
                            if t.id == st_id and formatted_search not in t.description:
                                t.description += formatted_search
            except Exception as ws_err:
                pass

        # Accumulate results for dependency tracking in the next iteration
        current_results.extend(batch_results)
        new_results.extend(batch_results)

    # Return the newly completed results to be appended to the state by the reducer
    return {"results": new_results}
