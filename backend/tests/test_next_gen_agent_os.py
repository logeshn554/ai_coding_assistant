import os
import sys
import pytest
import asyncio
import tempfile
import time

# Ensure backend root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_os.core.cache import CacheService
from agent_os.execution.lock_manager import FileLockManager
from agent_os.kernel.state_manager import StateManager
from agent_os.context.context_manager import WorkspaceContextManager
from agent_os.kernel.scheduler import DependencyScheduler
from agent_os.kernel.state_machine import TaskStateMachine

def test_cache_service():
    cache = CacheService()
    cache.set("embeddings", "query1", [0.1, 0.2, 0.3])
    assert cache.get("embeddings", "query1") == [0.1, 0.2, 0.3]
    
    # Test TTL expiration
    cache.set("completions", "prompt1", "response1", ttl=0.1)
    assert cache.get("completions", "prompt1") == "response1"
    time.sleep(0.15)
    assert cache.get("completions", "prompt1") is None
    
    # Test delete and clear
    cache.set("files", "path1", "content1")
    cache.delete("files", "path1")
    assert cache.get("files", "path1") is None
    
    cache.set("files", "path2", "content2")
    cache.clear()
    assert cache.get("files", "path2") is None


def test_lock_manager():
    lock_manager = FileLockManager()
    
    # Acquire exclusive lock
    assert lock_manager.acquire_lock("src/main.py", "AgentA", exclusive=True) is True
    assert lock_manager.is_locked("src/main.py") is True
    
    # Concurrently try to acquire same file lock with another agent
    assert lock_manager.acquire_lock("src/main.py", "AgentB", exclusive=True) is False
    
    # Release lock
    assert lock_manager.release_lock("src/main.py", "AgentA") is True
    assert lock_manager.is_locked("src/main.py") is False
    
    # Test optimistic locking with temporary file
    with tempfile.NamedTemporaryFile("w", delete=False) as temp:
        temp.write("initial content")
        temp_name = temp.name
        
    try:
        lock_manager.snapshot_file(temp_name)
        assert lock_manager.verify_optimistic_lock(temp_name) is True
        
        # Modify file
        with open(temp_name, "w") as f:
            f.write("modified content")
            
        # Should detect mismatch
        assert lock_manager.verify_optimistic_lock(temp_name) is False
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)


def test_state_manager():
    sm = TaskStateMachine()
    manager = StateManager(sm)
    
    manager.set_current_task("Refactor codebase")
    assert manager.current_task == "Refactor codebase"
    assert manager.task_status == "RUNNING"
    
    manager.add_active_agent("Coding Agent")
    assert "Coding Agent" in manager.active_agents
    
    manager.add_completed_step("Task planning", "Planner Agent", "plan details")
    assert len(manager.completed_steps) == 1
    assert manager.completed_steps[0]["agent"] == "Planner Agent"
    
    manager.add_error("Compilation failed")
    assert manager.task_status == "FAILED"
    assert "Compilation failed" in manager.errors


def test_context_manager():
    manager = WorkspaceContextManager(workspace_root="/home/user")
    assert manager.workspace_root == "/home/user"
    
    manager.add_retrieved_file("app.py", "import os")
    assert manager.retrieved_files["app.py"] == "import os"
    
    manager.add_message("user", "Hello assistant")
    assert len(manager.conversation_history) == 1
    assert manager.conversation_history[0]["role"] == "user"
    
    manager.add_active_symbol("main")
    assert "main" in manager.active_symbols
    
    manager.add_open_editor("app.py")
    assert "app.py" in manager.open_editors


@pytest.mark.asyncio
async def test_dependency_scheduler():
    scheduler = DependencyScheduler(concurrency_limit=2)
    
    # Task list: 1 -> 2 -> 3 (sequential), and 4 (independent)
    tasks = [
        {"id": 1, "dependencies": []},
        {"id": 2, "dependencies": [1]},
        {"id": 3, "dependencies": [2]},
        {"id": 4, "dependencies": []}
    ]
    
    executed_order = []
    
    async def execute_task(task):
        executed_order.append(task["id"])
        await asyncio.sleep(0.05)
        return f"Result {task['id']}"
        
    results = await scheduler.execute_graph(tasks, execute_task)
    
    assert results[1]["status"] == "success"
    assert results[2]["status"] == "success"
    assert results[3]["status"] == "success"
    assert results[4]["status"] == "success"
    
    # Check that task 1 started before 2, and 2 before 3
    assert executed_order.index(1) < executed_order.index(2)
    assert executed_order.index(2) < executed_order.index(3)
