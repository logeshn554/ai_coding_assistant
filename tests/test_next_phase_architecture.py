"""
Test Suite for Next Phase Architecture — WorkspacePolicy, TaskTransaction, Capability permissions, and Replay logs.
"""

import pytest
from backend.app.agent.security import WorkspacePolicy, Capability, DEFAULT_EXCLUDE_DIRS
from backend.app.merge.file_transaction import TaskTransaction, TransactionState
from backend.app.agent.task_memory import TaskMemory


def test_workspace_policy_capabilities_and_exclusions(tmp_path):
    policy = WorkspacePolicy(workspace_root=str(tmp_path))
    assert policy.has_capability(Capability.FILESYSTEM_READ)
    assert policy.has_capability(Capability.FILESYSTEM_WRITE)
    assert policy.is_excluded_directory(".git")
    assert policy.is_excluded_directory("node_modules")
    assert policy.is_excluded_file(".env")

    with pytest.raises(PermissionError):
        policy.validate_capability(Capability.TERMINAL_EXEC_PRIVILEGED)


def test_task_transaction_lifecycle():
    txn = TaskTransaction("tx_101", "Implement search indexer")
    assert txn.state == TransactionState.CREATED

    txn.begin()
    assert txn.state == TransactionState.PLANNED

    txn.execute()
    assert txn.state == TransactionState.EXECUTING

    txn.verify()
    assert txn.state == TransactionState.VERIFYING

    txn.commit()
    assert txn.state == TransactionState.COMMITTED


def test_task_memory_replay_export():
    mem = TaskMemory(goal="Fix authentication flow")
    mem.add_step("Parse auth.py", step_type="context")
    step2 = mem.add_step("Patch JWT secret check", step_type="implement")
    step2.mark_completed("Patched auth.py")

    log = mem.export_replay_log()
    assert log["goal"] == "Fix authentication flow"
    assert len(log["steps"]) == 2
    assert log["steps"][1]["status"] == "completed"
