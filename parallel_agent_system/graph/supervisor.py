from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver

from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import GraphState


# --- Import Real Nodes ---
from parallel_agent_system.graph.nodes.decompose import decompose_task_node
from parallel_agent_system.graph.nodes.router import route_node, run_agents_parallel_node


async def reduce_node(state: GraphState) -> dict:
    """Merges parallel agent execution results."""
    return {"status": "reducing"}


async def monitor_node(state: GraphState) -> dict:
    """Monitors cost, stuck state, and progress."""
    return {"status": "monitoring"}


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
