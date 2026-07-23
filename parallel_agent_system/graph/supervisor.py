from typing import Literal
from langgraph.graph import StateGraph, END, START
try:
    from langgraph.graph.state import CompiledStateGraph
except (ImportError, ModuleNotFoundError):
    try:
        from langgraph.graph import CompiledStateGraph
    except (ImportError, ModuleNotFoundError):
        from typing import Any
        CompiledStateGraph = Any
try:
    from langgraph.checkpoint.memory import MemorySaver
except (ImportError, ModuleNotFoundError):
    try:
        from langgraph.checkpoint import MemorySaver
    except (ImportError, ModuleNotFoundError):
        class MemorySaver:
            pass

from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import GraphState, SubTask, AgentResult
from parallel_agent_system.monitor.stuck_detector import StuckDetector


# --- Import Real Nodes ---
from parallel_agent_system.graph.nodes.decompose import decompose_task_node
from parallel_agent_system.graph.nodes.router import route_node, run_agents_parallel_node


async def reduce_node(state: GraphState) -> dict:
    """Merges parallel agent execution results and runs conflict checks."""
    results = state.get("results", [])
    subtasks = state.get("subtasks", [])
    global_cost = sum(r.cost_usd for r in results)
    
    # Conflict detection
    file_modifiers = {}  # file_path -> list of subtask IDs
    conflicts = []
    
    for r in results:
        for f in r.files_changed:
            if f not in file_modifiers:
                file_modifiers[f] = []
            file_modifiers[f].append(r.subtask_id)
            
    for f, subtasks_list in file_modifiers.items():
        if len(subtasks_list) > 1:
            conflicts.append(f"Conflict: File '{f}' was modified by multiple parallel subtasks: {', '.join(subtasks_list)}")
            
    messages = []
    failed_results = [r for r in results if r.status != "success"]
    complete = len(results) >= len(subtasks)
    
    if conflicts:
        from langchain_core.messages import AIMessage
        conflict_msg = "\n".join(conflicts)
        messages.append(AIMessage(content=f"⚠️ Parallel conflict detected!\n{conflict_msg}"))
        status = "failed"
    else:
        status = "complete" if complete and not failed_results else "running"
        
    return {
        "global_cost_usd": global_cost,
        "messages": messages,
        "status": status
    }


# ---------------------------------------------------------------------------
# Evaluator-optimizer: refine_node
#
# Positioned between reduce_node and monitor_node.  After every parallel
# execution batch the evaluator checks for high-severity signals emitted by
# review / security / test agents.  If issues are found AND cycles remain,
# it injects a new code SubTask carrying the reviewer feedback and routes
# back to run_agents.  Otherwise it passes through to monitor_node.
# ---------------------------------------------------------------------------

# Keywords that indicate a high-severity problem in free-text agent output.
_HIGH_SEVERITY_KEYWORDS = frozenset([
    "critical", "high severity", "high-severity",
    "securityerror", "security error",
    "FAILED", "error:", "exception:",
])


def _is_high_severity(result: AgentResult) -> bool:
    """Return True if an evaluator result carries a high-severity signal."""
    # Prefer the structured field when agents populate it.
    if result.severity and result.severity.lower() in ("high", "critical"):
        return True
    # Test-failure count is an unambiguous numeric signal.
    if result.test_failures > 0:
        return True
    # Fall back to keyword heuristics for agents that only emit prose output.
    lower_output = result.output.lower()
    return any(kw.lower() in lower_output for kw in _HIGH_SEVERITY_KEYWORDS)


async def refine_node(state: GraphState) -> dict:
    """
    Evaluator-optimizer node.  Runs after reduce_node on every execution batch.

    Decision logic:
    1. Collect completed evaluator results (review, security, test agents).
    2. If any carry a high-severity signal AND remaining cycles > 0:
       a. Aggregate all feedback messages into a single refinement prompt.
       b. Inject a new 'code' SubTask that includes the feedback as context.
       c. Increment refinement_cycles and route back to run_agents.
    3. Otherwise route forward to monitor_node (clean pass or cycle cap reached).
    """
    from uuid import uuid4
    from langchain_core.messages import AIMessage

    config = SystemConfig()
    max_cycles = config.max_refinement_cycles
    current_cycles: int = state.get("refinement_cycles", 0)

    results = state.get("results", [])
    evaluator_types = {"review", "security", "test"}

    # Collect evaluator results from the *latest* batch (successful runs only).
    evaluator_results = [
        r for r in results
        if r.agent_type in evaluator_types and r.status == "success"
    ]

    high_severity_results = [r for r in evaluator_results if _is_high_severity(r)]

    needs_refinement = bool(high_severity_results) and current_cycles < max_cycles

    if not needs_refinement:
        # Nothing to fix, or cycle cap reached — let monitor_node decide completion.
        if current_cycles >= max_cycles and high_severity_results:
            from langchain_core.messages import AIMessage as _AIMessage
            return {
                "messages": [_AIMessage(
                    content=(
                        f"⚠️ Refinement cycle cap reached ({max_cycles}). "
                        "Remaining high-severity issues were not resolved. "
                        "Proceeding to completion check."
                    )
                )]
            }
        return {}

    # ---- Build aggregated feedback for the Coding Agent ----
    feedback_lines = []
    for r in high_severity_results:
        header = f"[{r.agent_type.upper()} AGENT — subtask {r.subtask_id[:8]}]"
        body = r.output[:2000]  # cap to avoid inflating context window
        if r.severity:
            body = f"Severity: {r.severity.upper()}\n{body}"
        if r.test_failures:
            body = f"Test failures: {r.test_failures}\n{body}"
        feedback_lines.append(f"{header}\n{body}")

    aggregated_feedback = "\n\n".join(feedback_lines)
    goal = state.get("goal", "the current task")

    refinement_description = (
        f"[REFINEMENT CYCLE {current_cycles + 1}/{max_cycles}] "
        f"Fix all high-severity issues raised by the evaluators for: {goal}\n\n"
        f"--- EVALUATOR FEEDBACK ---\n{aggregated_feedback}"
    )

    # Inject a new code SubTask carrying the feedback.
    new_subtask_id = str(uuid4())
    new_subtask = SubTask(
        id=new_subtask_id,
        agent_type="code",
        description=refinement_description,
        workspace_dir=f"/workspace/refine-{new_subtask_id[:8]}",
        priority=100,  # highest priority — runs first in next batch
        depends_on=[],
    )

    refine_log = AIMessage(
        content=(
            f"🔄 Refinement cycle {current_cycles + 1}/{max_cycles} triggered. "
            f"{len(high_severity_results)} high-severity evaluator result(s) found. "
            "Re-routing to Coding Agent with feedback."
        )
    )

    return {
        "subtasks": state.get("subtasks", []) + [new_subtask],
        "refinement_cycles": current_cycles + 1,
        "status": "running",
        "messages": [refine_log],
    }


def route_after_refine(state: GraphState) -> str:
    """Routes to run_agents if there are pending unexecuted subtasks (e.g. injected by refine_node), otherwise to monitor."""
    subtasks = state.get("subtasks", [])
    results = state.get("results", [])
    completed_ids = {r.subtask_id for r in results}
    has_pending = any(t.id not in completed_ids for t in subtasks)
    if has_pending:
        return "retry"
    return "monitor"



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
    graph.add_node("refine", refine_node)   # evaluator-optimizer
    graph.add_node("monitor", monitor_node)

    # Static transitions: decompose → route → run_agents → reduce → refine
    graph.add_edge(START, "decompose")
    graph.add_edge("decompose", "route")
    graph.add_edge("route", "run_agents")
    graph.add_edge("run_agents", "reduce")
    graph.add_edge("reduce", "refine")

    # refine branches: re-run if high-severity issues remain, otherwise proceed to monitor
    graph.add_conditional_edges("refine", route_after_refine, {
        "retry": "run_agents",
        "monitor": "monitor",
    })

    # monitor branches: END on complete/failed, retry run_agents on running
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
    try:
        return graph.compile(checkpointer=checkpointer, interrupt_before=["monitor"])
    except TypeError:
        try:
            return graph.compile(interrupt_before=["monitor"])
        except TypeError:
            return graph.compile()
