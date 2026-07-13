"""A very small stub implementation of the `langgraph.graph` module.
It defines the constants and classes used by the project's orchestrator.
The implementation is intentionally minimal – it only needs to satisfy
imports and basic usage in the test suite. It does **not** aim to provide
full graph execution capabilities.
"""

# Constants representing the start and end nodes of a graph.
START = "START"
END = "END"


class StateGraph:
    """Simple placeholder for the real ``StateGraph`` class.

    The orchestrator uses the following methods:
    - ``add_node(name, fn)``
    - ``add_edge(src, dst)``
    - ``add_conditional_edges(node, fn, mapping)``
    - ``compile()`` which returns an object with an async ``ainvoke`` method.

    This stub stores the provided information but does not implement a full
    graph engine. The ``ainvoke`` method performs a very basic execution flow
    sufficient for the unit tests that only verify node functions directly.
    """

    def __init__(self, state_type):
        self.state_type = state_type
        self.nodes = {}
        self.edges = {}
        self.conditional = {}

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def add_edge(self, src, dst):
        self.edges.setdefault(src, []).append(dst)

    def add_conditional_edges(self, node, fn, mapping):
        # Store the routing function and the mapping of possible routes.
        self.conditional[node] = (fn, mapping)

    def compile(self):
        """Return a compiled graph with an ``ainvoke`` coroutine.

        The real library builds an asynchronous execution engine. For the
        purposes of the tests we only need to invoke the ``Orchestrator``
        node and respect the ``route_next`` conditional logic. The stub
        therefore executes the start node, calls the associated function,
        applies the conditional routing once, and returns the resulting
        state.
        """

        graph = self

        class CompiledGraph:
            def __init__(self, graph):
                self.graph = graph

            async def ainvoke(self, state):
                # Begin at the START edge if defined.
                next_nodes = self.graph.edges.get(START, [])
                if not next_nodes:
                    return state
                # Follow the first edge from START.
                current = next_nodes[0]
                # Execute the node function.
                fn = self.graph.nodes.get(current)
                if fn is None:
                    return state
                state = await fn(state)
                # Apply conditional routing if defined for this node.
                if current in self.graph.conditional:
                    cond_fn, mapping = self.graph.conditional[current]
                    route = cond_fn(state)
                    # If the route resolves to END, finish.
                    if route == END:
                        return state
                return state

        return CompiledGraph(graph)
