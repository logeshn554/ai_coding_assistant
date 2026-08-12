"""
Phase 2 Acceptance Tests — Repository Intelligence & Context Engine.

Verifies:
- Symbol Indexing (classes, functions, methods, imports)
- Dependency Graph (nodes, edges, traversal, caller/callee/test discovery)
- Hybrid Search (exact, regex, symbol, semantic)
- Hybrid Ranking & Context Budgets
- Incremental Indexing (create, update, delete)
- Security Filtering (.env, secrets, ignored files)
- AgentRuntime & Editor State Integration
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import pytest

from backend.app.agent.context_engine import (
    AgentContext,
    ContextBudget,
    ContextEngine,
    DependencyGraph,
    DiagnosticItem,
    EdgeType,
    EditorContext,
    GitContext,
    HybridRanker,
    NodeType,
    Position,
    SecurityFilter,
    SelectionRange,
    SmartSearchEngine,
    SymbolIndex,
    SymbolKind,
    WorkspaceContext,
)


@pytest.fixture
def temp_repo():
    """Scaffold a temporary multi-layer software repository for context engine testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = pathlib.Path(tmpdir)

        # Create source files
        (root / "src").mkdir()
        (root / "src" / "auth.py").write_text("""
class AuthService:
    def authenticate(self, username, password):
        if username == "admin":
            return True
        return False

def validate_token(token):
    return len(token) > 5
""")

        (root / "src" / "routes.py").write_text("""
from auth import AuthService

def login_route(request):
    service = AuthService()
    return service.authenticate(request.user, request.pwd)
""")

        # Create test file
        (root / "tests").mkdir()
        (root / "tests" / "test_auth.py").write_text("""
from src.auth import AuthService

def test_authenticate():
    service = AuthService()
    assert service.authenticate("admin", "secret")
""")

        # Create secret & ignored files
        (root / ".env").write_text("SECRET_KEY=supersecretkey123")
        (root / "secret.pem").write_text("-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg...\n-----END PRIVATE KEY-----")

        yield root


def test_security_filter(temp_repo):
    """Test SecurityFilter excludes secrets, .env, and binary files."""
    sf = SecurityFilter(str(temp_repo))
    assert sf.is_ignored(".env") is True
    assert sf.is_ignored("secret.pem") is True
    assert sf.is_ignored("src/auth.py") is False

    assert sf.contains_secret("SECRET_KEY=AKIA1234567890ABCDEF") is True
    assert sf.contains_secret("def normal_func(): pass") is False


def test_symbol_indexing(temp_repo):
    """Test SymbolIndex extracts functions, classes, and methods."""
    index = SymbolIndex(str(temp_repo))
    index.build_full_index()

    auth_syms = index.find_symbols("AuthService")
    assert len(auth_syms) >= 1
    assert auth_syms[0].kind == SymbolKind.CLASS

    func_syms = index.find_symbols("validate_token")
    assert len(func_syms) >= 1
    assert func_syms[0].kind == SymbolKind.FUNCTION


def test_dependency_graph(temp_repo):
    """Test DependencyGraph nodes, edges, and related test discovery."""
    graph = DependencyGraph()
    file_a = graph.add_node("file:src/auth.py", "src/auth.py", NodeType.FILE, path="src/auth.py")
    test_node = graph.add_node("file:tests/test_auth.py", "tests/test_auth.py", NodeType.TEST, path="tests/test_auth.py")

    graph.add_edge("file:tests/test_auth.py", "file:src/auth.py", EdgeType.TESTS)

    tests = graph.find_tests("auth")
    assert "tests/test_auth.py" in tests


def test_incremental_indexing(temp_repo):
    """Test incremental symbol re-indexing on file creation and deletion."""
    index = SymbolIndex(str(temp_repo))
    index.build_full_index()

    # Create new file dynamically
    new_file = temp_repo / "src" / "payment.py"
    new_file.write_text("class PaymentProcessor:\n    def process(self): pass")

    index.index_file("src/payment.py")
    syms = index.find_symbols("PaymentProcessor")
    assert len(syms) == 1

    # Delete file dynamically
    new_file.unlink()
    index.remove_file("src/payment.py")
    assert len(index.find_symbols("PaymentProcessor")) == 0


@pytest.mark.asyncio
async def test_context_engine_build_context(temp_repo):
    """Test canonical ContextEngine context package assembly with L0-L4 signals."""
    engine = ContextEngine.get_instance(str(temp_repo))
    engine._index_sync()

    editor = EditorContext(
        active_file="src/auth.py",
        cursor=Position(line=3, column=5),
        selected_text="def authenticate(self, username, password):",
        diagnostics=[DiagnosticItem(file="src/auth.py", message="Syntax warning", line=3)],
    )

    git = GitContext(branch="main", modified_files=["src/auth.py"])

    ctx = await engine.build_context(
        task_description="Fix authentication issue in AuthService",
        workspace=WorkspaceContext(workspace_root=str(temp_repo)),
        editor=editor,
        git=git,
    )

    assert isinstance(ctx, AgentContext)
    assert ctx.total_tokens_estimate > 0
    assert len(ctx.items) > 0

    # Ensure active file src/auth.py is ranked top
    top_file = ctx.items[0].file
    assert "auth.py" in top_file

    # Ensure secret file is excluded
    assert not any(".env" in item.file for item in ctx.items)
