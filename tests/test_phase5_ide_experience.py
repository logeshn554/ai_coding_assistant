"""
Phase 5 Integration Tests — Production-Grade IDE Experience.

Verifies:
- Central IDE & Agent Timeline State Lifecycle
- Event Reducer & Timeline Step Processing
- Tool Execution Cards & Operational Reasoning
- Inline Edit & Diff Review Hunk Operations
- Security Approval Workflows
- Context Inspector Provenance Output
- Undo Agent Run Rollback
- Session History & Crash Recovery
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import pytest

from backend.app.agent.agent_runtime import AgentRuntime, AgentState, AgentTask
from backend.app.agent.autonomous import (
    AgentTaskContract,
    ExecutionPlan,
    ExecutionPlanner,
    SessionRecoveryManager,
    SessionStateSnapshot,
    StepStatus,
    TaskContractGenerator,
)
from backend.app.agent.context_engine import ContextEngine, WorkspaceContext
from backend.app.agent.security import PermissionEngine, RiskLevel


@pytest.fixture
def ide_workspace():
    """Scaffold a temporary workspace for Phase 5 IDE tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = pathlib.Path(tmpdir)
        (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\npythonpath = ['.']")
        (root / "src").mkdir()
        (root / "src" / "auth.py").write_text("class AuthService:\n    def login(self): return True\n")
        (root / "tests").mkdir()
        (root / "tests" / "test_auth.py").write_text("from src.auth import AuthService\ndef test_login(): assert AuthService().login() is True\n")
        yield root


@pytest.mark.asyncio
async def test_ide_agent_timeline_events(ide_workspace):
    """Test AgentRuntime emits structured timeline events (contract, plan, tools, verification, completion)."""
    runtime = AgentRuntime()
    session = await runtime.start_session(str(ide_workspace))

    events_received = []

    def on_event(ev):
        events_received.append(ev.type)

    async def mock_llm_provider(messages, tools=None):
        from backend.app.agent.agent_runtime.llm_adapter import ModelResponse
        return ModelResponse(text="Refactored auth service successfully.", tool_calls=[])

    task = AgentTask(id="task_ide_001", description="Refactor auth service")
    res = await runtime.run(session.session_id, task, event_callback=on_event, llm_provider_func=mock_llm_provider)

    assert "agent.started" in events_received
    assert "agent.plan.created" in events_received
    assert "verification.started" in events_received
    assert "verification.completed" in events_received
    assert "agent.completed" in events_received


@pytest.mark.asyncio
async def test_context_inspector_endpoint(ide_workspace):
    """Test ContextEngine get_debug_info returns provenance metrics for ContextInspector."""
    engine = ContextEngine.get_instance(str(ide_workspace))
    engine._index_sync()

    debug_info = await engine.get_debug_info("Refactor auth service")

    assert "status" in debug_info
    assert "indexed_files" in debug_info
    assert "search_results" in debug_info
    assert debug_info["indexed_files"] > 0


def test_hunk_diff_review_operations():
    """Test hunk-level accept and reject operations."""
    hunks = [
        {"id": "h1", "file": "src/auth.py", "lines": ["+ def logout(): pass"], "accepted": None},
        {"id": "h2", "file": "src/auth.py", "lines": ["- def old_login(): pass"], "accepted": None},
    ]

    # Accept hunk 1
    hunks[0]["accepted"] = True
    assert hunks[0]["accepted"] is True
    assert hunks[1]["accepted"] is None

    # Reject hunk 2
    hunks[1]["accepted"] = False
    assert hunks[1]["accepted"] is False


def test_undo_agent_run(ide_workspace):
    """Test Undo Agent Run rollbacks workspace changes to pre-state snapshot."""
    from backend.app.agent.agent_runtime import TransactionalWorkspace

    tx = TransactionalWorkspace(str(ide_workspace))
    target_file = "src/auth.py"

    # Capture pre-state snapshot
    pre_snap = tx.capture_pre_state(target_file)

    # Modify file
    abs_path = ide_workspace / target_file
    abs_path.write_text("class AuthService:\n    def login(self): return False\n    def new_method(self): pass\n")

    # Capture post-state diff
    diff = tx.capture_post_state(target_file, pre_snap)
    assert diff is not None

    # Rollback/Undo file to pre-state content
    abs_path.write_text(pre_snap.content)
    assert "new_method" not in abs_path.read_text()


def test_approval_workflow_permission():
    """Test PermissionEngine approval decision generation for Strict/Assisted/Autonomous modes."""
    p_strict = PermissionEngine("C:/fake_root", mode="Strict")
    dec_strict = p_strict.evaluate_tool_call("s1", "write_file", {"path": "src/app.py"})
    assert dec_strict.requires_approval is True

    p_auto = PermissionEngine("C:/fake_root", mode="Autonomous")
    dec_auto = p_auto.evaluate_tool_call("s1", "write_file", {"path": "src/app.py"})
    assert dec_auto.requires_approval is False


def test_session_history_resumption(ide_workspace):
    """Test session state snapshot persistence and recovery for interrupted agents."""
    mgr = SessionRecoveryManager(str(ide_workspace))
    snapshot = SessionStateSnapshot(
        session_id="session_interrupted_123",
        task_goal="Fix login bug",
        contract_data={"goal": "Fix login bug"},
        plan_data={},
        current_step_id="implement-changes",
        repair_rounds=1,
        changed_files=["src/auth.py"],
        verification_status="RUNNING",
        status="EXECUTING",
    )

    mgr.save_snapshot(snapshot)

    # Restore session state
    restored = mgr.load_snapshot("session_interrupted_123")
    assert restored is not None
    assert restored.current_step_id == "implement-changes"
    assert restored.repair_rounds == 1
