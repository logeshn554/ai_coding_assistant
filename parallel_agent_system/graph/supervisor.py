from typing import Literal
from langgraph.graph import StateGraph, END
try:
    from langgraph.graph.state import CompiledStateGraph
except (ImportError, ModuleNotFoundError):
    try:
        from langgraph.graph import CompiledStateGraph
    except (ImportError, ModuleNotFoundError):
        from typing import Any
        CompiledStateGraph = Any
from langgraph.checkpoint.memory import MemorySaver

from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import GraphState


# --- Import Real Nodes ---
from parallel_agent_system.graph.nodes.decompose import decompose_task_node
from parallel_agent_system.graph.nodes.router import route_node, run_agents_parallel_node


async def reduce_node(state: GraphState) -> dict:
    """Merges parallel agent execution results and runs conflict checks."""
    results = state.get("results", [])
    global_cost = sum(r.cost_usd for r in results)
    
    # Conflict detection
    file_modifiers = {}  # file_path -> list of subtask IDs
    conflicts = []
    
    for r in results:
        for f in r.files_changed:
            if f not in file_modifiers:
                file_modifiers[f] = []
            file_modifiers[f].append(r.subtask_id)
            
    for f, subtasks in file_modifiers.items():
        if len(subtasks) > 1:
            conflicts.append(f"Conflict: File '{f}' was modified by multiple parallel subtasks: {', '.join(subtasks)}")
            
    messages = []
    status = "reducing"
    if conflicts:
        from langchain_core.messages import AIMessage
        conflict_msg = "\n".join(conflicts)
        messages.append(AIMessage(content=f"⚠️ Parallel conflict detected!\n{conflict_msg}"))
        status = "failed"
        
    return {
        "global_cost_usd": global_cost,
        "messages": messages,
        "status": status
    }


async def monitor_node(state: GraphState) -> dict:
    """Monitors global budgets (cost & iterations) and determines graph completion status."""
    from parallel_agent_system.core.config import SystemConfig
    config = SystemConfig()
    
    # 1. Budget checks
    global_cost = state.get("global_cost_usd", 0.0)
    if global_cost > config.max_global_cost_usd:
        from langchain_core.messages import AIMessage
        return {
            "status": "failed",
            "messages": [AIMessage(content=f"❌ Global cost budget exceeded: ${global_cost:.2f} > ${config.max_global_cost_usd:.2f}")]
        }
        
    iteration = state.get("iteration", 0)
    if iteration > config.max_retries:
        from langchain_core.messages import AIMessage
        return {
            "status": "failed",
            "messages": [AIMessage(content=f"❌ Iteration retry limit exceeded: {iteration} > {config.max_retries}")]
        }
        
    # 2. Check if all subtasks are finished successfully
    subtasks = state.get("subtasks", [])
    results = state.get("results", [])
    
    results_map = {r.subtask_id: r for r in results}
    
    all_success = True
    any_failed = False
    for st in subtasks:
        res = results_map.get(st.id)
        if not res:
            all_success = False
        else:
            if res.status != "success":
                any_failed = True
                all_success = False
                
    if all_success:
        return {"status": "complete"}
    elif any_failed:
        if iteration < config.max_retries:
            return {
                "status": "running",
                "iteration": iteration + 1
            }
        else:
            return {"status": "failed"}
    else:
        return {"status": "running"}


def route_after_monitor(state: GraphState) -> str:
    """Decides next graph destination after the monitor node."""
    status = state.get("status")
    if status == "complete":
        return "complete"
    elif status == "running":
        return "retry"
    elif status == "monitoring":
        return "human"
    else:
        return "failed"


# --- Graph Construction ---

def build_supervisor_graph(config: SystemConfig) -> CompiledStateGraph:
    """
    Builds the CompiledStateGraph for multi-agent supervision.
    Integrates checking mechanism and sets interrupts before the monitor node.
    """
    graph = StateGraph(GraphState)

    # Register nodes
    graph.add_node("decompose", decompose_task_node)
    graph.add_node("route", route_node)
    graph.add_node("run_agents", run_agents_parallel_node)
    graph.add_node("reduce", reduce_node)
    graph.add_node("monitor", monitor_node)

    # Setup static transitions
    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "route")
    graph.add_edge("route", "run_agents")
    graph.add_edge("run_agents", "reduce")
    graph.add_edge("reduce", "monitor")

    # Setup conditional transitions from the monitor node
    graph.add_conditional_edges("monitor", route_after_monitor, {
        "complete": END,
        "retry": "run_agents",
        "human": "monitor",
        "failed": END,
    })

    # Setup checkpointer
    if config.postgres_url and not config.postgres_url.startswith("mock://"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            # Use connection string to instantiate PostgresSaver
            # Note: For production execution. Unit tests use MemorySaver.
            checkpointer = PostgresSaver.from_conn_string(config.postgres_url)
        except Exception:
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()

    # Compile the graph with interrupt before the monitor node for human-in-the-loop
    return graph.compile(checkpointer=checkpointer, interrupt_before=["monitor"])
