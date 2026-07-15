import asyncio
from typing import Any

from parallel_agent_system.core.state import SubTask, AgentResult, GraphState
from parallel_agent_system.core.config import SystemConfig


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
        batch_results = await asyncio.gather(
            *[run_one(t) for t in pending_batch],
            return_exceptions=False
        )

        # Accumulate results for dependency tracking in the next iteration
        current_results.extend(batch_results)
        new_results.extend(batch_results)

    # Return the newly completed results to be appended to the state by the reducer
    return {"results": new_results}
