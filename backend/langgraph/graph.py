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

    def compile(self, *args, **kwargs):
        graph = self

        class CompiledGraph:
            def __init__(self, graph):
                self.graph = graph

            async def ainvoke(self, state, config=None, **kwargs):
                next_nodes = self.graph.edges.get(START, [])
                if not next_nodes:
                    return state
                current = next_nodes[0]
                
                max_steps = 100
                step = 0
                while current and current != END and step < max_steps:
                    step += 1
                    fn = self.graph.nodes.get(current)
                    if fn is None:
                        break
                    state = await fn(state)
                    
                    if current in self.graph.conditional:
                        cond_fn, mapping = self.graph.conditional[current]
                        route = cond_fn(state)
                        
                        if isinstance(route, list):
                            # Parallel execution of nodes in list
                            for target in route:
                                target_node = mapping.get(target, target)
                                if target_node != END and target_node in self.graph.nodes:
                                    target_fn = self.graph.nodes[target_node]
                                    state = await target_fn(state)
                            # After parallel nodes execute, return to Orchestrator if static edge exists
                            # Or default back to Orchestrator
                            current = "Orchestrator"
                        else:
                            target_node = mapping.get(route, route)
                            if target_node == END:
                                break
                            current = target_node
                    elif current in self.graph.edges and self.graph.edges[current]:
                        current = self.graph.edges[current][0]
                    else:
                        break

                return state

        return CompiledGraph(graph)
