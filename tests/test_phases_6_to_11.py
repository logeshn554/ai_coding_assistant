"""
Phases 6 to 11 Integration & Verification Test Suite.

Verifies:
- Phase 6: AST Symbol Indexing, SymbolGraph Relations, Impact Analysis & Background Indexing
- Phase 7: Specialized Agent Roles, Contracts, Budgets & Debate Review Loop
- Phase 8: DebugContext Analysis, Root Cause Diagnosis & Breakpoint AI
- Phase 9: Smart Test Selection, Quality Analysis & Regression Test Generation
- Phase 10: Git Change Attribution, 3-Way Merge Conflict Parsing & PR Summaries
- Phase 11: Durable Project Memory Persistence & Fact Invalidation
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import pytest

from backend.app.agent.context_engine.code_intelligence import (
    ASTAnalyzer,
    BackgroundIndexer,
    ImpactAnalyzer,
    SymbolDefinition,
    SymbolGraph,
    SymbolRelation,
)
from backend.app.agent.autonomous.role_capabilities import (
    AgentRole,
    DebateReviewLoop,
    ROLE_CONTRACTS,
    RoleBudget,
)
from backend.app.agent.debugging.ai_debugger import (
    AIDebugger,
    DebugContext,
    StackFrame,
)
from backend.app.agent.testing.quality_engine import (
    RegressionTestGenerator,
    SmartTestSelector,
    TestQualityAnalyzer,
)
from backend.app.agent.git.git_collaboration import (
    GitCollaborationEngine,
    MergeConflictSection,
)
from backend.app.agent.context_engine.project_memory import (
    ProjectFact,
    ProjectMemoryStore,
)


@pytest.fixture
def p6_11_workspace():
    """Scaffold a temporary workspace for Phases 6-11 tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = pathlib.Path(tmpdir)

        (root / "src").mkdir()
        (root / "src" / "service.py").write_text(
            "import os\n\n"
            "class UserService:\n"
            "    def get_user(self, uid):\n"
            "        return self.query_db(uid)\n"
            "    def query_db(self, uid):\n"
            "        return {'id': uid}\n"
        )
        (root / "tests").mkdir()
        (root / "tests" / "test_service.py").write_text(
            "from src.service import UserService\n\n"
            "def test_user():\n"
            "    assert True\n"
            "    srv = UserService()\n"
            "    assert srv.get_user(1)['id'] == 1\n"
        )

        yield root


def test_phase6_ast_and_impact_analysis(p6_11_workspace):
    """Test AST symbol extraction, SymbolGraph relations, and ImpactAnalyzer blast radius."""
    code = (p6_11_workspace / "src" / "service.py").read_text()
    symbols, relations = ASTAnalyzer.analyze_python_file("src/service.py", code)

    assert len(symbols) >= 3  # UserService, get_user, query_db
    assert any(s.name == "UserService" and s.kind == "class" for s in symbols)
    assert any(s.name == "get_user" and s.kind == "function" for s in symbols)

    graph = SymbolGraph()
    for s in symbols:
        graph.add_symbol(s)
    for r in relations:
        graph.add_relation(r)

    impact_analyzer = ImpactAnalyzer(graph)
    report = impact_analyzer.calculate_impact("query_db", "src/service.py")

    assert report.target_symbol == "query_db"
    assert "get_user" in report.affected_callers


@pytest.mark.asyncio
async def test_phase6_background_indexer(p6_11_workspace):
    """Test non-blocking BackgroundIndexer scans repository."""
    indexer = BackgroundIndexer(str(p6_11_workspace))
    await indexer.index_workspace_async()

    assert indexer.indexed_files_count >= 2
    assert indexer.pending_files_count == 0


def test_phase7_role_contracts_and_debate_loop():
    """Test specialized agent role contracts, budgets, and DebateReviewLoop."""
    coder_contract = ROLE_CONTRACTS[AgentRole.CODER]
    assert "write_file" in coder_contract.allowed_tools
    assert coder_contract.budget.max_repair_rounds == 5

    # Debate Review Loop
    valid_diff = "--- a/src/app.py\n+++ b/src/app.py\n+ def fix(): pass"
    approved, msg = DebateReviewLoop.evaluate_proposal(valid_diff, ["Fix bug"])
    assert approved is True

    secret_diff = "+ AWS_SECRET = '12345'"
    rejected, secret_msg = DebateReviewLoop.evaluate_proposal(secret_diff, ["Fix bug"])
    assert rejected is False
    assert "credentials" in secret_msg.lower()


def test_phase8_ai_debugger_and_breakpoint():
    """Test DebugContext root cause analysis and breakpoint variable evaluation."""
    frame = StackFrame(
        filename="src/service.py",
        line_no=5,
        function_name="get_user",
        local_vars={"uid": 1, "user_obj": None},
    )
    ctx = DebugContext(
        process_id=1024,
        thread_id=1,
        exception_type="NullPointerException",
        exception_message="user_obj is null",
        stack_frames=[frame],
    )

    diagnosis = AIDebugger.analyze_debug_context(ctx)
    assert diagnosis.culprit_file == "src/service.py"
    assert diagnosis.culprit_line == 5

    ans = AIDebugger.evaluate_breakpoint_variable(ctx, "user_obj")
    assert "evaluates to 'None'" in ans or "user_obj" in ans


def test_phase9_smart_test_selector_and_quality():
    """Test SmartTestSelector, TestQualityAnalyzer weak assertions, and RegressionTestGenerator."""
    graph = SymbolGraph()
    graph.add_relation(SymbolRelation("src/service.py", "tests/test_service.py", "depends-on", "tests/test_service.py"))

    selected = SmartTestSelector.select_relevant_tests(["src/service.py"], graph, ["tests/test_service.py"])
    assert "tests/test_service.py" in selected

    # Quality Analysis
    test_code = "def test_foo():\n    assert True\n    assert 1 == 1\n"
    q_report = TestQualityAnalyzer.analyze_test_file("tests/test_foo.py", test_code)
    assert q_report.weak_assertions_count >= 2

    # Regression test generation
    reg_test = RegressionTestGenerator.generate_regression_test("get_user", "Fix null user", "+ return {}")
    assert "def test_regression_get_user" in reg_test


def test_phase10_git_collaboration_and_conflict():
    """Test AI change attribution, 3-way merge conflict parsing, and PR summary."""
    attrib = GitCollaborationEngine.attribute_changes(["src/service.py", "src/user.py"], ["src/service.py"])
    assert "src/service.py" in attrib.ai_modified_files
    assert "src/user.py" in attrib.user_modified_files

    conflict_text = (
        "<<<<<<< HEAD\n"
        "def login(): return True\n"
        "=======\n"
        "def login(): return False\n"
        ">>>>>>> feature"
    )
    parsed = GitCollaborationEngine.parse_merge_conflict("src/service.py", conflict_text)
    assert parsed.ours_content.strip() == "def login(): return True"
    assert parsed.theirs_content.strip() == "def login(): return False"

    summary = GitCollaborationEngine.generate_prepare_change_summary("Refactor auth", ["src/service.py"], True)
    assert summary.verification_passed is True
    assert "refactor auth" in summary.commit_message.lower()


def test_phase11_project_memory_and_invalidation(p6_11_workspace):
    """Test ProjectMemoryStore fact persistence and invalidation when source file changes."""
    store = ProjectMemoryStore(str(p6_11_workspace))
    fact = store.add_fact("architecture", "Auth uses UserService", "src/service.py")

    assert len(store.get_valid_facts()) == 1

    # Invalidate when source file is modified
    invalidated = store.invalidate_source_file("src/service.py")
    assert fact.fact_id in invalidated
    assert len(store.get_valid_facts()) == 0
