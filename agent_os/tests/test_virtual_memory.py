import pytest
from agent_os.context.virtual_memory import VirtualMemoryContextManager

def test_virtual_memory_context_pools():
    # 1. Budget of 100 tokens (400 chars)
    manager = VirtualMemoryContextManager(token_budget=100)

    manager.load_context("current_func", "def add(x, y): return x + y", "hot")
    manager.load_context("tests", "def test_add(): assert add(1, 2) == 3", "warm")
    manager.load_context("git_history", "commit 1: initial commit", "cold")

    assert manager._hot["current_func"] == "def add(x, y): return x + y"
    assert manager._warm["tests"] == "def test_add(): assert add(1, 2) == 3"
    assert manager._cold["git_history"] == "commit 1: initial commit"

    # Verify token estimations (character size // 4)
    assert manager.estimate_tokens("current_func") == 27 // 4
    assert manager.estimate_tokens() == (27 + 38 + 25) // 4

def test_virtual_memory_promote_demote():
    manager = VirtualMemoryContextManager(token_budget=1000)

    manager.load_context("plan", "Step 1: Code, Step 2: Test", "cold")
    assert "plan" in manager._cold

    # Promote: cold -> warm
    manager.promote("plan")
    assert "plan" in manager._warm
    assert "plan" not in manager._cold

    # Promote: warm -> hot
    manager.promote("plan")
    assert "plan" in manager._hot
    assert "plan" not in manager._warm

    # Demote: hot -> warm
    manager.demote("plan")
    assert "plan" in manager._warm

    # Demote: warm -> cold
    manager.demote("plan")
    assert "plan" in manager._cold

def test_virtual_memory_paging_eviction():
    # Strict budget: 35 tokens (140 characters)
    manager = VirtualMemoryContextManager(token_budget=35)

    # Load items that fit within the budget
    # 42 chars = 10 tokens
    manager.load_context("patch", "diff --git a/file.py b/file.py\n+new line", "hot")
    # 27 chars = 6 tokens
    manager.load_context("plan", "Step 1: Modify, Step 2: Run", "warm")
    # 14 chars = 3 tokens
    manager.load_context("history", "commit 1: init", "cold")

    # Total chars = 83. 83 // 4 = 20 tokens
    assert manager.estimate_tokens() == 20

    # Load a large Hot item (67 chars = 16 tokens)
    # This should evict the Cold item ("history") but keep the Warm item ("plan")
    manager.load_context("current_file", "import os\nimport sys\ndef run():\n    print('Running kernel state')\n", "hot")

    assert manager.estimate_tokens() <= 35
    # "history" (cold) should be evicted to fit new Hot item
    assert "history" not in manager._cold
    
    # "plan" (warm) should remain in Warm Context
    assert "plan" in manager._warm
    assert "patch" in manager._hot
    assert "current_file" in manager._hot

    # Prompt payload formatting contains pool boundaries
    payload = manager.get_prompt_payload()
    assert "[HOT CONTEXT]" in payload
    assert "[COLD CONTEXT]" not in payload
