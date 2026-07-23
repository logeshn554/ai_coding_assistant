"""A minimal stub of the ``langgraph.graph`` module required for unit tests.
Gated by DEVPILOT_TEST_MODE=1.
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
                state_copy = dict(state)
                while current and current != END and step < max_steps:
                    step += 1
                    fn = self.graph.nodes.get(current)
                    if fn is None:
                        break
                    res = await fn(state_copy)
                    if isinstance(res, dict):
                        for k, v in res.items():
                            if k == "results" and k in state_copy and isinstance(state_copy[k], list) and isinstance(v, list):
                                state_copy[k] = state_copy[k] + v
                            elif k == "messages" and k in state_copy and isinstance(state_copy[k], list) and isinstance(v, list):
                                state_copy[k] = state_copy[k] + v
                            else:
                                state_copy[k] = v
                    
                    if current in self.graph.conditional:
                        cond_fn, mapping = self.graph.conditional[current]
                        route = cond_fn(state_copy)
                        
                        if isinstance(route, list):
                            for target in route:
                                target_node = mapping.get(target, target)
                                if target_node != END and target_node in self.graph.nodes:
                                    target_fn = self.graph.nodes[target_node]
                                    t_res = await target_fn(state_copy)
                                    if isinstance(t_res, dict):
                                        for k, v in t_res.items():
                                            if k == "results" and k in state_copy and isinstance(state_copy[k], list) and isinstance(v, list):
                                                state_copy[k] = state_copy[k] + v
                                            else:
                                                state_copy[k] = v
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

                return state_copy

        return CompiledGraph(graph)
