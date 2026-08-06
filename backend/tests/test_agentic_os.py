import sys
import time
import asyncio
import pytest
from pathlib import Path

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 1. Gateway imports
from app.gateway.auth import auth_gateway, AuthMethod
from app.gateway.rate_limiter import rate_limiter, RateLimitResult
from app.gateway.circuit_breaker import circuit_breaker_registry, CircuitState
from app.gateway.streaming import stream_manager
from app.gateway.session_manager import gateway_session_manager, SessionState

# 2. Kernel imports
from agent_os.kernel.budget_manager import budget_manager, BudgetScope, BudgetAlert
from agent_os.kernel.health_monitor import health_monitor, HealthStatus
from agent_os.kernel.cancellation_manager import cancellation_manager
from agent_os.kernel.policy_engine import policy_engine
from agent_os.kernel.state_machine import TaskStateMachine

# 3. Infrastructure imports
from agent_os.infrastructure.durable_event_bus import durable_event_bus
from agent_os.infrastructure.workflow_store import workflow_store
from agent_os.infrastructure.observability import observability
from agent_os.infrastructure.secret_store import secret_store
from agent_os.infrastructure.audit_store import audit_store
from agent_os.infrastructure.metrics import metrics_collector
from agent_os.infrastructure.distributed_tracing import distributed_tracer
from agent_os.infrastructure.configuration import configuration

# 4. Intelligence imports
from app.intelligence.intent_compiler import intent_compiler
from app.intelligence.contract_generator import contract_generator

# 5. Brain imports
from app.brain.versioned_memory import versioned_memory
from app.brain.symbol_graph import symbol_graph
from app.brain.knowledge_graph import knowledge_graph
from app.brain.dependency_graph import dependency_graph
from app.brain.api_graph import api_graph
from app.brain.test_graph import test_graph
from app.brain.architecture_graph import architecture_graph
from app.brain.team_style_memory import team_style_memory
from app.brain.decision_memory import decision_memory
from app.brain.bug_history import bug_history
from app.brain.cognitive_cache import cognitive_cache

# 6. Analysis imports
from app.analysis.impact_analyzer import impact_analyzer
from app.analysis.dependency_resolver import dependency_resolver
from app.analysis.symbol_resolver import symbol_resolver
from app.analysis.prediction_engine import prediction_engine

# 7. Work Graph imports
from app.work_graph.capability_planner import capability_planner
from app.work_graph.dag_generator import dag_generator
from app.work_graph.semantic_lock import semantic_lock
from app.work_graph.lease_manager import lease_manager
from app.work_graph.priority_scheduler import priority_scheduler
from app.work_graph.retry_planner import retry_planner

# 8. Routing imports
from app.adapters.router import agent_reputation_engine, cost_optimizer, latency_optimizer, provider_health_monitor

# 9. Patch & Merge imports
from app.patch.patch_store import patch_store
from app.patch.patch_metadata import PatchMetadata
from app.merge.symbol_merge import symbol_merge
from app.merge.contract_validator import contract_validator
from app.merge.conflict_detector import conflict_detector
from app.merge.file_transaction import file_transaction
from app.merge.rollback_engine import rollback_engine

# 10. Verification & Debate & Repair imports
from app.verification.test_runner import test_runner
from app.verification.type_checker import type_checker
from app.verification.lint_runner import lint_runner
from app.verification.security_scanner import security_scanner
from app.verification.architecture_rules import architecture_rules
from app.debate.debate_engine import debate_engine
from app.debate.consensus import consensus_engine
from app.repair.root_cause_analyzer import root_cause_analyzer
from app.repair.self_evolving_prompts import self_evolving_prompts
from app.repair.continuous_learning import continuous_learning

# 11. Outcome & Release imports
from app.outcome.outcome_classifier import outcome_classifier, OutcomeGrade
from app.outcome.release_gate import release_gate
from app.release.git_committer import git_committer
from app.release.summary_generator import summary_generator


# ── TEST CASES ──────────────────────────────────────────────────────────────

def test_gateway_auth():
    """Verify AuthGateway token parsing, environment keys, and default identities."""
    headers = {"Authorization": "Bearer some-invalid-token"}
    identity = auth_gateway.authenticate(headers=headers)
    assert identity.auth_method == AuthMethod.ANONYMOUS
    assert "admin" in identity.roles


def test_gateway_rate_limiter():
    """Verify sliding window, limit counters, and Retry-After headers."""
    # First request
    resp = rate_limiter.check("tenant-1", "user-1", "/api/chat", tier="free")
    assert resp.result == RateLimitResult.ALLOWED
    assert resp.remaining > 0

    # Exhaust limit
    for _ in range(30):
        resp = rate_limiter.check("tenant-1", "user-1", "/api/chat", tier="free")

    assert resp.result == RateLimitResult.THROTTLED
    assert resp.retry_after > 0


def test_gateway_circuit_breaker():
    """Verify circuit breaker transitions from CLOSED to OPEN on error count."""
    breaker = circuit_breaker_registry.get_or_create("openai-api")
    assert breaker.state == CircuitState.CLOSED

    # Register 10 failures
    for _ in range(10):
        breaker.record_failure("HTTP timeout")

    assert breaker.state == CircuitState.OPEN
    assert not breaker.can_execute()


def test_gateway_session_manager():
    """Verify session lifecycle and TTL expiry checks."""
    session = gateway_session_manager.create_session("tenant-a", "user-a", workspace_root="/tmp")
    assert session.state == SessionState.CREATED
    assert session.is_alive

    gateway_session_manager.activate_session(session.session_id)
    retrieved = gateway_session_manager.get_session(session.session_id)
    assert retrieved.state == SessionState.ACTIVE


def test_kernel_budget_manager():
    """Verify token and dollar budget limits and alert thresholds."""
    budget_manager.allocate(BudgetScope.SESSION, "sess-1", max_cost_usd=1.0)
    
    # Consume within limit
    alloc = budget_manager.consume(BudgetScope.SESSION, "sess-1", cost_usd=0.5)
    assert not alloc.is_exhausted
    assert alloc.cost_remaining == 0.5

    # Exceed budget
    alloc = budget_manager.consume(BudgetScope.SESSION, "sess-1", cost_usd=0.6)
    assert alloc.is_exhausted


def test_kernel_health_monitor():
    """Verify worker registrations, heartbeats, and status changes."""
    health = health_monitor.register_worker("worker-1", "code", "Writing unit test")
    assert health.status == HealthStatus.HEALTHY

    health_monitor.heartbeat("worker-1")
    assert health.heartbeat_count == 1


def test_kernel_cancellation_manager():
    """Verify CancellationToken propagation and callback execution."""
    cancellation_manager.register_task("task-1")
    cancelled = []
    
    cancellation_manager.add_cancellation_callback("task-1", lambda tid, r: cancelled.append(tid))
    cancellation_manager.cancel_task("task-1", "Test cancellation")
    
    assert cancellation_manager.is_cancelled("task-1")
    assert "task-1" in cancelled


def test_kernel_policy_engine():
    """Verify sandbox boundaries and path protection rules."""
    policy_engine.workspace_root = "e:/os kernel with ani"
    assert policy_engine.is_path_safe("e:/os kernel with ani/backend/app/main.py")
    # Outside workspace path should fail
    assert not policy_engine.is_path_safe("c:/windows/system32/cmd.exe")


def test_durable_event_bus():
    """Verify event log durability, sync publication, and event replaying."""
    events = []
    durable_event_bus.subscribe("test_event", lambda ev: events.append(ev))
    
    # Publish event
    asyncio.run(durable_event_bus.publish("test_event", {"val": 42}))
    assert len(events) == 1
    assert events[0].data["val"] == 42
    
    # Replay check
    replayed = durable_event_bus.replay(since_sequence_id=1)
    assert len(replayed) >= 1


def test_observability_spans():
    """Verify timing context managers record durations correctly."""
    with observability.span("db_query", {"table": "users"}):
        time.sleep(0.01)

    spans = observability.get_spans()
    assert len(spans) >= 1
    assert spans[-1]["name"] == "db_query"
    assert spans[-1]["duration_ms"] > 0


def test_intelligence_intent_compiler():
    """Verify rule-based goal, constraint, and risk translation."""
    compiled = intent_compiler.compile("Implement write_file logic. It must create the directory path. Make sure to test it.")
    assert "write_file" in compiled.goal
    assert any("must" in c.lower() or "create" in c.lower() for c in compiled.constraints)
    assert any("test" in ac.lower() for ac in compiled.acceptance_criteria)


def test_brain_versioned_memory():
    """Verify memory retrieval conforms to versioning properties."""
    versioned_memory.set("active_agent", "DevPilot-Agent-V1")
    val = versioned_memory.get("active_agent")
    assert val == "DevPilot-Agent-V1"


def test_symbol_graph_ast():
    """Verify class/function definitions indexing."""
    code = "class TestClass:\n    pass\ndef test_fn():\n    pass"
    symbol_graph.parse_file("test.py", code)
    assert "TestClass" in symbol_graph.nodes
    assert "test_fn" in symbol_graph.nodes


def test_work_graph_priority_scheduler():
    """Verify scheduled tasks transition safely."""
    from app.work_graph.dag_generator import DagTask
    task_a = DagTask(task_id="a", description="Task A", agent_type="code")
    task_b = DagTask(task_id="b", description="Task B", agent_type="test", dependencies=["a"])
    
    priority_scheduler.load_dag([task_a, task_b])
    ready = priority_scheduler.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "a"

    # Mark A success
    priority_scheduler.mark_success("a")
    ready = priority_scheduler.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "b"


def test_outcome_classifier():
    """Verify evidence calculations and release gate routing decisions."""
    res = outcome_classifier.classify_outcome(
        test_failures=0,
        lint_passed=True,
        type_checks_passed=True,
        security_passed=True,
        contract_violations=[]
    )
    assert res.grade == OutcomeGrade.SUCCESS
    assert release_gate.should_auto_release(res)
