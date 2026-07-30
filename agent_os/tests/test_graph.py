import os
import tempfile
import pytest
from agent_os.repository.repository import RepositoryKernel
from agent_os.repository.graph import RepositoryKnowledgeGraph

def test_knowledge_graph_relationships():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a dummy multi-file structure
        helper_path = os.path.join(tmpdir, "helper.py")
        main_path = os.path.join(tmpdir, "main.py")
        test_path = os.path.join(tmpdir, "test_main.py")

        helper_code = """
class MathLib:
    pass

def add_numbers(x, y):
    return x + y
"""
        main_code = """
import helper
from helper import MathLib

def compute():
    lib = MathLib()
    val = helper.add_numbers(10, 20)
    return val
"""
        test_code = """
import main

def test_compute():
    res = main.compute()
    assert res == 30
"""
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write(helper_code)
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(main_code)
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        # 2. Scan workspace
        kernel = RepositoryKernel()
        kernel.scan_workspace(tmpdir)

        # 3. Instantiate Graph
        graph = RepositoryKnowledgeGraph(kernel)

        # 4. Test getDependencies (camelCase and snake_case)
        deps = graph.getDependencies("main.py")
        assert "helper.py" in deps["imports"]
        assert "test_main.py" in deps["imported_by"]

        # 5. Test getCallGraph
        cg_add = graph.get_call_graph("add_numbers")
        # add_numbers does not call any other functions defined
        assert len(cg_add["calls"]) == 0
        # add_numbers is called by compute
        assert any(c["name"] == "compute" for c in cg_add["called_by"])

        cg_compute = graph.getCallGraph("compute")
        # compute calls add_numbers
        assert any(c["name"] == "add_numbers" for c in cg_compute["calls"])
        # compute is called by test_compute
        assert any(c["name"] == "test_compute" for c in cg_compute["called_by"])

        # 6. Test getImpactAnalysis (transitive closure)
        # Changing add_numbers impacts compute and test_compute!
        impact = graph.getImpactAnalysis("add_numbers")
        assert "compute" in impact["symbols"]
        assert "test_compute" in impact["symbols"]
        assert "main.py" in impact["files"]
        assert "test_main.py" in impact["files"]

        # 7. Test getRelatedSymbols
        related = graph.getRelatedSymbols("compute")
        assert "MathLib" in related
        assert "add_numbers" in related
