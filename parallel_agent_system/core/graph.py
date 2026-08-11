"""
Native DAG Executor — A lightweight, compatible implementation of StateGraph and CompiledStateGraph.

Replaces the langgraph library with a native python execution engine.

Supports:
  - Sequential node execution with conditional routing
  - **Parallel fan-out groups**: independent nodes declared via ``add_parallel_group``
    are executed concurrently via ``asyncio.gather`` and their state updates merged.
  - In-memory checkpointing with ``MemorySaver``
  - Human-in-the-loop interrupts
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import operator
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union

logger = logging.getLogger("parallel_agent_system.core.graph")

START = "__start__"
END = "__end__"

try:
    from langgraph.graph.message import add_messages
except (ImportError, ModuleNotFoundError):
    try:
        from langgraph.graph import add_messages
    except (ImportError, ModuleNotFoundError):
        def add_messages(left, right):
            return left + right


class MemorySaver:
    """In-memory checkpointer saving graph execution states."""

    def __init__(self) -> None:
        self._checkpoints: Dict[str, Dict[str, Any]] = {}

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._checkpoints.get(thread_id)

    def put(self, thread_id: str, state: Dict[str, Any]) -> None:
        # Deep copy simulation to prevent reference mutations
        import copy
        try:
            self._checkpoints[thread_id] = copy.deepcopy(state)
        except Exception:
            # Fallback to copy if deepcopy fails on complex/unserializable attributes
            self._checkpoints[thread_id] = copy.copy(state)


class CompiledStateGraph:
    """Compiled native state graph ready for execution.

    Supports both sequential edges and **parallel fan-out groups** where
    independent nodes execute concurrently via ``asyncio.gather``.
    """

    def __init__(
        self,
        nodes: Dict[str, Callable],
        edges: Dict[str, str],
        conditional_edges: Dict[str, Tuple[Callable, Dict[str, str]]],
        parallel_groups: Dict[str, List[str]],
        parallel_group_exit_edges: Dict[str, str],
        checkpointer: Optional[MemorySaver] = None,
        interrupt_before: Optional[List[str]] = None,
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.parallel_groups = parallel_groups  # group_id -> [node_name, ...]
        self.parallel_group_exit_edges = parallel_group_exit_edges  # group_id -> next_node
        self.checkpointer = checkpointer or MemorySaver()
        self.interrupt_before = interrupt_before or []

    async def ainvoke(self, initial_state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke the graph asynchronously."""
        config = config or {}
        thread_id = config.get("configurable", {}).get("thread_id", "")

        # 1. Load from checkpoint or initialize
        checkpoint = None
        if thread_id:
            checkpoint = self.checkpointer.get(thread_id)

        if checkpoint:
            state = checkpoint
            current_node = state.get("__current_node__", START)
            # Clear interrupt flag to resume
            state["human_confirmation_required"] = False
        else:
            state = dict(initial_state)
            current_node = START

        logger.info(f"Native Graph: Starting execution at node '{current_node}'")

        # Main execution loop
        while current_node != END:
            # Resolve START edge
            if current_node == START:
                current_node = self.edges.get(START, END)
                if current_node == END:
                    break

            # ── Check if current_node is a parallel group ──
            if current_node in self.parallel_groups:
                group_id = current_node
                member_nodes = self.parallel_groups[group_id]
                logger.info(f"Native Graph: Executing parallel group '{group_id}' with nodes {member_nodes}")

                async def _exec_member(node_name: str) -> Optional[dict]:
                    action = self.nodes.get(node_name)
                    if not action:
                        logger.error(f"Native Graph Error: Parallel member node '{node_name}' not registered.")
                        return None
                    if inspect.iscoroutinefunction(action):
                        return await action(state)
                    else:
                        return action(state)

                # Fan-out: execute all members concurrently
                member_results = await asyncio.gather(
                    *[_exec_member(n) for n in member_nodes],
                    return_exceptions=True
                )

                # Merge all results back into state
                for i, result in enumerate(member_results):
                    if isinstance(result, Exception):
                        logger.error(f"Native Graph: Parallel node '{member_nodes[i]}' raised: {result}")
                        state["status"] = "failed"
                        if "messages" not in state:
                            state["messages"] = []
                        try:
                            from langchain_core.messages import AIMessage
                            state["messages"].append(AIMessage(content=f"Error in parallel node {member_nodes[i]}: {result}"))
                        except ImportError:
                            pass
                    elif isinstance(result, dict):
                        self._merge_state(state, result)

                # Determine next node from the parallel group exit edge
                current_node = self.parallel_group_exit_edges.get(group_id, END)
                state["__current_node__"] = current_node

                if thread_id:
                    self.checkpointer.put(thread_id, state)
                continue

            # Handle human-in-the-loop interrupts
            if current_node in self.interrupt_before and not state.get("__resumed_from_interrupt__", False):
                logger.info(f"Native Graph: Interrupting execution before node '{current_node}'")
                state["__current_node__"] = current_node
                state["__resumed_from_interrupt__"] = True
                state["human_confirmation_required"] = True
                if thread_id:
                    self.checkpointer.put(thread_id, state)
                return state

            # Reset the interrupt resume flag once we execute past the node
            state["__resumed_from_interrupt__"] = False

            # Execute the node action
            node_action = self.nodes.get(current_node)
            if not node_action:
                logger.error(f"Native Graph Error: Node '{current_node}' action not registered.")
                break

            logger.debug(f"Native Graph: Executing node '{current_node}'")
            try:
                if inspect.iscoroutinefunction(node_action):
                    update = await node_action(state)
                else:
                    update = node_action(state)
            except Exception as e:
                logger.error(f"Native Graph Error executing node '{current_node}': {e}")
                state["status"] = "failed"
                if "messages" not in state:
                    state["messages"] = []
                try:
                    from langchain_core.messages import AIMessage
                    state["messages"].append(AIMessage(content=f"Error executing {current_node}: {e}"))
                except ImportError:
                    pass
                break

            # Merge update into state with reducer awareness
            if isinstance(update, dict):
                self._merge_state(state, update)

            # Determine next node
            next_node = None
            if current_node in self.edges:
                next_node = self.edges[current_node]
            elif current_node in self.conditional_edges:
                router_fn, path_map = self.conditional_edges[current_node]
                try:
                    if inspect.iscoroutinefunction(router_fn):
                        router_result = await router_fn(state)
                    else:
                        router_result = router_fn(state)
                    next_node = path_map.get(router_result, END)
                except Exception as e:
                    logger.error(f"Native Graph: Conditional edge routing failed from '{current_node}': {e}")
                    next_node = END
            else:
                next_node = END

            current_node = next_node
            state["__current_node__"] = current_node

            # Save checkpoint
            if thread_id:
                self.checkpointer.put(thread_id, state)

        logger.info(f"Native Graph: Execution finished. Final status: '{state.get('status')}'")
        return state

    def _merge_state(self, state: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Merge dictionary state, applying custom list/message reducers if defined."""
        for k, v in update.items():
            if k == "results":
                state["results"] = state.get("results", []) + v
            elif k == "messages":
                state["messages"] = add_messages(state.get("messages", []), v)
            elif k == "subtasks":
                # Ensure no duplicate subtasks are added
                existing_ids = {t.id for t in state.get("subtasks", [])}
                new_tasks = [t for t in v if t.id not in existing_ids]
                state["subtasks"] = state.get("subtasks", []) + new_tasks
            else:
                state[k] = v


class StateGraph:
    """A native implementation of StateGraph with parallel fan-out support.

    Use ``add_parallel_group`` to declare independent nodes that should
    execute concurrently.  The compiled graph will run them via
    ``asyncio.gather`` and merge their state updates.
    """

    def __init__(self, state_schema: Any) -> None:
        self.state_schema = state_schema
        self.nodes: Dict[str, Callable] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, Tuple[Callable, Dict[str, str]]] = {}
        # Parallel fan-out groups
        self._parallel_groups: Dict[str, List[str]] = {}  # group_id -> [node_names]
        self._parallel_group_exit_edges: Dict[str, str] = {}  # group_id -> next_node

    def add_node(self, name: str, action: Callable) -> None:
        self.nodes[name] = action

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.edges[from_node] = to_node

    def add_conditional_edges(self, from_node: str, router_fn: Callable, path_map: Dict[str, str]) -> None:
        self.conditional_edges[from_node] = (router_fn, path_map)

    def add_parallel_group(
        self,
        group_id: str,
        node_names: List[str],
        exit_to: str = END,
    ) -> None:
        """Declare a set of nodes that should execute in parallel.

        When the graph reaches ``group_id`` (use it like a virtual node name in
        ``add_edge``), all ``node_names`` will be dispatched concurrently via
        ``asyncio.gather``.  After all complete, execution continues to
        ``exit_to``.

        All member nodes must already be registered via ``add_node``.
        """
        for n in node_names:
            if n not in self.nodes:
                raise ValueError(f"Parallel group '{group_id}' references unregistered node '{n}'")
        self._parallel_groups[group_id] = list(node_names)
        self._parallel_group_exit_edges[group_id] = exit_to

    def compile(
        self,
        checkpointer: Optional[MemorySaver] = None,
        interrupt_before: Optional[List[str]] = None,
    ) -> CompiledStateGraph:
        return CompiledStateGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
            parallel_groups=self._parallel_groups,
            parallel_group_exit_edges=self._parallel_group_exit_edges,
            checkpointer=checkpointer,
            interrupt_before=interrupt_before
        )
