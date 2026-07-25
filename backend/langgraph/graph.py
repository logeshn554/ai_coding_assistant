import os
import sys
import importlib.util

if os.environ.get("DEVPILOT_TEST_MODE") == "1":
    from ._test_stub import START, END, StateGraph
else:
    real_found = False
    for path in sys.path:
        norm_p = os.path.normcase(path)
        if "backend" in norm_p and "site-packages" not in norm_p:
            continue
        spec_path = os.path.join(path, "langgraph", "graph", "__init__.py")
        if not os.path.exists(spec_path):
            spec_path = os.path.join(path, "langgraph", "graph.py")
        if os.path.exists(spec_path) and os.path.normcase(os.path.abspath(spec_path)) != os.path.normcase(os.path.abspath(__file__)):
            try:
                spec = importlib.util.spec_from_file_location("real_langgraph_graph", spec_path)
                if spec and spec.loader:
                    real_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(real_mod)
                    START = getattr(real_mod, "START", "START")
                    END = getattr(real_mod, "END", "END")
                    StateGraph = getattr(real_mod, "StateGraph", None)
                    real_found = True
                    break
            except Exception:
                pass
    if not real_found:
        from ._test_stub import START, END, StateGraph

__all__ = ["START", "END", "StateGraph"]
