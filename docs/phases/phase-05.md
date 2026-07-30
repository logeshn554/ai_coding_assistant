# Phase 5: Context Virtual Memory

## Goal
Enforce token containment rules using Hot, Warm, Cold context pools and LRU paging.

## Achievements
*   Implemented `VirtualMemoryContextManager` in `agent_os/context/virtual_memory.py`.
*   Structured context sections: Hot (file/func/patch/diagnostics), Warm (neighbors/tests/plan), Cold (repo/graph/git history).
*   Enforced cascading LRU evictions to fit the target prompt token budget limit.

## Verification
*   `test_virtual_memory.py`
