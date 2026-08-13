"""
Test Suite for Complete Production Features — PatchEngine, SymbolMerger, AST WorkspaceIndex, and CheckpointManager.
"""

import pytest
from backend.app.patch_engine import PatchEngine
from backend.app.merge.symbol_merge import SymbolMerger
from backend.app.workspace_index import WorkspaceIndex
from backend.app.agent.agent_os.agent.checkpoint_manager import CheckpointManager


def test_patch_engine_hunk_parsing_and_application():
    original = "def hello():\n    return 'old'\n"
    diff = "@@ -1,2 +1,2 @@\n def hello():\n-    return 'old'\n+    return 'new'\n"

    patched = PatchEngine.apply_patch(original, diff)
    assert "return 'new'" in patched
    assert "return 'old'" not in patched


def test_symbol_merger_ast_aware_replacement():
    base = "def greet():\n    return 'hello'\n\ndef farewell():\n    return 'bye'\n"
    patch = "def greet():\n    return 'hello world'\n"

    merged = SymbolMerger.merge_python_sources(base, patch)
    assert "hello world" in merged
    assert "farewell" in merged


def test_workspace_index_ast_symbol_extraction(tmp_path):
    py_file = tmp_path / "sample.py"
    py_file.write_text("class MyService:\n    def execute(self):\n        pass\n", encoding="utf-8")

    index = WorkspaceIndex(str(tmp_path))
    symbols = index.get_symbols("sample.py")
    assert len(symbols) >= 2
    symbol_names = [s["name"] for s in symbols]
    assert "MyService" in symbol_names
    assert "execute" in symbol_names


def test_checkpoint_manager_snapshot_creation(tmp_path):
    mgr = CheckpointManager(str(tmp_path))
    mgr.save_checkpoint("run_1", "task_1", "agent_1", "att_1", "running", None, [{"event": "start"}], ["msg1", "msg2"], ["app.py"], {})

    snapshot_id = mgr.create_snapshot("run_1", "v1.0", "Release snapshot")
    assert "snapshot-v1.0" in snapshot_id
