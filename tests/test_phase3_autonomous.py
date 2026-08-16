"""
Phase 3 Autonomous Coding, Verification, and Self-Repair Integration Tests — Step 29 requirement.

Verifies:
- Task Contract & Execution Planning
- VerificationEngine & Scoped Profiles
- Failure Classification & ContextEngine Connection
- Self-Repair Loop & Bounded Budgets
- Loop Detection (Repeated Failure Protection)
- Change-Set Validation & Scope Protection
- Agent Reviewer & Acceptance Criteria Evaluation
- Command Safety & Mode Policy Integration
- Crash Recovery & Session Resumption
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import pytest

from backend.app.agent.agent_runtime import AgentRuntime, AgentState, AgentTask
from backend.app.agent.autonomous import (
    AgentReviewer,
    AgentTaskContract,
    ChangeSetValidator,
    CommandRiskLevel,
    ExecutionMode,
    ExecutionPlanner,
    FailureAnalyzer,
    FailureCategory,
    PolicyEngine,
    SelfRepairLoop,
    SessionRecoveryManager,
    SessionStateSnapshot,
    StepStatus,
    TaskContractGenerator,
    VerificationEngine,
    VerificationFailure,
    VerificationResult,
)


@pytest.fixture
def temp_workspace():
    """Scaffold temporary project workspace with pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = pathlib.Path(tmpdir)
        (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\npythonpath = ['.']\nminversion = '6.0'")
        (root / "src").mkdir()
        (root / "src" / "math_utils.py").write_text("def add(a, b):\n    return a + b\n")
        (root / "tests").mkdir()
        (root / "tests" / "test_math.py").write_text("from src.math_utils import add\ndef test_add():\n    assert add(1, 2) == 3\n")
        yield root


def test_task_contract_generation():
    """Test TaskContractGenerator creates structured contracts with risk levels."""
    contract = TaskContractGenerator.create_contract("Add login endpoint to auth subsystem")
    assert isinstance(contract, AgentTaskContract)
    assert contract.risk_level == "MEDIUM"
    assert len(contract.acceptance_criteria) >= 2


def test_execution_planner():
    """Test ExecutionPlanner creates executable multi-step plans."""
    contract = TaskContractGenerator.create_contract("Refactor user repository")
    plan = ExecutionPlanner.generate_plan(contract)

    assert len(plan.steps) == 3
    assert plan.steps[0].status == StepStatus.PENDING

    plan.mark_step_status("investigate-context", StepStatus.COMPLETED)
    assert plan.steps[0].status == StepStatus.COMPLETED
    assert plan.get_next_step().id == "implement-changes"


@pytest.mark.asyncio
async def test_verification_engine_profile(temp_workspace):
    """Test VerificationEngine detects Python profile and runs scoped verification."""
    v_engine = VerificationEngine(str(temp_workspace))
    assert v_engine.profile.language == "python"

    res = await v_engine.run_scoped_verification(test_files=["tests/test_math.py"])
    assert isinstance(res, VerificationResult)
    assert res.success is True


def test_failure_analyzer():
    """Test FailureAnalyzer parses raw terminal error logs into structured VerificationFailure."""
    raw_error = "File \"src/auth.py\", line 42, in login\nSyntaxError: invalid syntax"
    failure = FailureAnalyzer.analyze_output("pytest", raw_error)

    assert failure.category == FailureCategory.SYNTAX
    assert failure.file == "src/auth.py"
    assert failure.line == 42


def test_self_repair_loop_and_repeated_failure():
    """Test SelfRepairLoop enforces repair budgets and detects repeated failure loops."""
    contract = AgentTaskContract(goal="Fix bug", max_repair_rounds=3)
    repair_loop = SelfRepairLoop(contract)

    failure1 = VerificationFailure(command="pytest", category=FailureCategory.UNIT_TEST, file="test.py", line=10, message="Assert failed")

    assert repair_loop.can_attempt_repair() is True

    # Attempt 1
    assert repair_loop.detect_failure_loop(failure1) is False
    repair_loop.record_repair_attempt(failure1, "patch 1", False)

    # Attempt 2 — Repeated identical failure
    is_loop = repair_loop.detect_failure_loop(failure1)
    assert is_loop is True


def test_change_set_validator(temp_workspace):
    """Test ChangeSetValidator flags secret file modifications and out-of-scope edits."""
    contract = AgentTaskContract(goal="Fix math bug", scope=["math"])

    # Secret edit check
    res_secret = ChangeSetValidator.validate_changes([".env"], contract)
    assert res_secret.valid is False
    assert res_secret.requires_review is True

    # In-scope edit check
    res_valid = ChangeSetValidator.validate_changes(["src/math_utils.py"], contract)
    assert res_valid.valid is True


def test_agent_reviewer():
    """Test AgentReviewer evaluates acceptance criteria and distinguishes verification from review."""
    contract = AgentTaskContract(
        goal="Add math helper",
        acceptance_criteria=["Syntax check passed", "Targeted tests pass"],
    )
    v_res = VerificationResult(success=True, command="pytest", output="PASSED", duration_seconds=1.0)

    review = AgentReviewer.review_task(contract, ["src/math_utils.py"], v_res)
    assert review.approved is True
    assert review.confidence >= 0.90


def test_policy_engine():
    """Test PolicyEngine command risk classification and execution modes."""
    assert PolicyEngine.classify_command_risk("pytest tests/") == CommandRiskLevel.LOW
    assert PolicyEngine.classify_command_risk("rm -rf src/") == CommandRiskLevel.HIGH

    # Strict mode requires approval for HIGH risk
    assert PolicyEngine.is_approval_required(ExecutionMode.STRICT, CommandRiskLevel.HIGH) is True
    assert PolicyEngine.is_approval_required(ExecutionMode.AUTONOMOUS, CommandRiskLevel.LOW) is False


def test_session_recovery(temp_workspace):
    """Test SessionRecoveryManager saves and restores session state snapshot cleanly."""
    mgr = SessionRecoveryManager(str(temp_workspace))
    snapshot = SessionStateSnapshot(
        session_id="test_sess_123",
        task_goal="Fix bug",
        contract_data={"goal": "Fix bug"},
        plan_data={},
        current_step_id="step_1",
        repair_rounds=2,
        changed_files=["src/math_utils.py"],
        verification_status="PASSED",
        status="EXECUTING",
    )

    saved_path = mgr.save_snapshot(snapshot)
    assert os.path.exists(saved_path)

    restored = mgr.load_snapshot("test_sess_123")
    assert restored is not None
    assert restored.session_id == "test_sess_123"
    assert restored.repair_rounds == 2


@pytest.mark.asyncio
async def test_agent_runtime_autonomous_workflow(temp_workspace):
    """Test end-to-end AgentRuntime autonomous execution with verification and state transitions."""
    runtime = AgentRuntime()
    session = await runtime.start_session(str(temp_workspace))

    async def mock_llm_provider(messages, tools=None):
        from backend.app.agent.agent_runtime.llm_adapter import ModelResponse
        return ModelResponse(text="Completed verification of math utils.", tool_calls=[])

    task = AgentTask(id="task_001", description="Verify math utils")
    res = await runtime.run(session.session_id, task, llm_provider_func=mock_llm_provider)

    assert res.state in (AgentState.COMPLETED, AgentState.COMPLETED_VERIFIED, AgentState.COMPLETED_WITH_WARNINGS)
    assert res.verification_status.value == "PASSED"
