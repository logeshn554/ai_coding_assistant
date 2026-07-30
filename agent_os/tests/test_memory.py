import os
import tempfile
import pytest
from agent_os.learning.memory_kernel import MemoryKernelManager

def test_memory_kernel_management():
    manager = MemoryKernelManager()

    # 1. Test initial empty states
    assert manager.get_current_task() is None
    assert manager.get_current_plan() is None
    assert manager.get_repository_state() is None
    assert len(manager.get_artifacts()) == 0
    assert len(manager.get_events()) == 0
    assert manager.get_current_patch() is None
    assert len(manager.get_diagnostics()) == 0

    # 2. Test setters, getters, and adders
    manager.set_current_task("Implement memory storage")
    manager.set_current_plan({"steps": ["Define schema", "Write tests"]})
    manager.set_repository_state({"changed_files": ["memory.py"]})
    manager.add_artifact("plan_doc", {"type": "markdown", "content": "# Plan"})
    manager.add_event("action_executed", {"action": "write"})
    manager.set_current_patch({"path": "memory.py", "diff": "@@ -1 +1 @@"})
    manager.set_diagnostics([{"severity": "error", "message": "SyntaxError"}])

    assert manager.get_current_task() == "Implement memory storage"
    assert manager.get_current_plan() == {"steps": ["Define schema", "Write tests"]}
    assert manager.get_repository_state() == {"changed_files": ["memory.py"]}
    assert manager.get_artifacts()["plan_doc"] == {"type": "markdown", "content": "# Plan"}
    assert len(manager.get_events()) == 1
    assert manager.get_events()[0]["type"] == "action_executed"
    assert manager.get_current_patch() == {"path": "memory.py", "diff": "@@ -1 +1 @@"}
    assert len(manager.get_diagnostics()) == 1

    # 3. Test memory cleanup (clear_all)
    manager.clear_all()
    assert manager.get_current_task() is None
    assert len(manager.get_artifacts()) == 0
    assert len(manager.get_events()) == 0

def test_memory_kernel_persistence():
    manager = MemoryKernelManager()
    manager.set_current_task("Task to persist")
    manager.set_current_plan({"id": 42})
    manager.add_artifact("manifest", {"version": "1.0"})
    manager.add_event("system_boot", {"timestamp": 12345})
    manager.set_diagnostics([])

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "state.json")
        
        # Persist to file
        manager.persist_to_disk(filepath)
        assert os.path.exists(filepath)

        # Clear and verify empty
        manager.clear_all()
        assert manager.get_current_task() is None

        # Load from file
        manager.load_from_disk(filepath)
        assert manager.get_current_task() == "Task to persist"
        assert manager.get_current_plan() == {"id": 42}
        assert manager.get_artifacts()["manifest"] == {"version": "1.0"}
        assert len(manager.get_events()) == 1
        assert manager.get_events()[0]["payload"] == {"timestamp": 12345}
