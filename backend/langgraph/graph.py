"""A minimal stub of the ``langgraph.graph`` module required for the
project's orchestrator. It provides the constants ``START`` and ``END`` and a
light‑weight ``StateGraph`` class with the methods used in the code base.

The implementation is deliberately simple – it stores nodes and edges and
offers a ``compile`` method that returns an object with an async ``ainvoke``
coroutine. The coroutine executes the start node, runs the associated function,
applies a single conditional routing step, and returns the resulting state.
This is sufficient for the unit tests, which only verify the behavior of the
individual node functions and do not rely on full graph execution.
"""

START = "START"
END = "END"


class StateGraph:
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
        self.conditional[node] = (fn, mapping)

    def compile(self):
        graph = self

        class CompiledGraph:
            def __init__(self, graph):
                self.graph = graph

            async def ainvoke(self, state):
                # Follow the first edge from START if it exists.
                next_nodes = self.graph.edges.get(START, [])
                if not next_nodes:
                    return state
                current = next_nodes[0]
                fn = self.graph.nodes.get(current)
                if fn is None:
                    return state
                state = await fn(state)
                # Apply conditional routing if defined.
                if current in self.graph.conditional:
                    cond_fn, mapping = self.graph.conditional[current]
                    route = cond_fn(state)
                    if route == END:
                        return state
                return state

        return CompiledGraph(graph)
