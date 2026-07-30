import pytest
from agent_os.learning.engine import LearningEngine

def test_learning_engine_storage_and_queries():
    engine = LearningEngine()

    # 1. Store structured fixes
    engine.store_fix(
        error_type="SyntaxError",
        file_path="main.py",
        error_msg="Unexpected indentation error on line 42",
        solution_diff="@@ -42 +42 @@\n-   print()\n+    print()"
    )
    engine.store_fix(
        error_type="ConnectionError",
        file_path="db.py",
        error_msg="Connection timed out to Postgres DB",
        solution_diff="@@ -2 +2 @@\n-timeout=1\n+timeout=10"
    )

    # 2. Store other structured metadata
    engine.store_summary("my_project", {"files_count": 10, "language": "python"})
    engine.store_convention("indentation", "Enforce 4 spaces indentation across python files.")
    engine.store_performance("AST scan", 0.045, 1200)

    # 3. Verify similarity query on fixes
    # "indentation on main" should match SyntaxError fix
    matches = engine.find_similar_fixes("unexpected indentation error")
    assert len(matches) == 1
    assert matches[0]["error_type"] == "SyntaxError"
    assert matches[0]["similarity_score"] > 0.0

    # "Postgres connection" should match ConnectionError fix
    db_matches = engine.find_similar_fixes("timed out postgres connection")
    assert len(db_matches) == 1
    assert db_matches[0]["error_type"] == "ConnectionError"

def test_learning_engine_pattern_search():
    engine = LearningEngine()

    # Store pattern items
    engine.store_pattern("Dependency Injection Container", "DI Architectural Pattern", "class DI:")
    engine.store_pattern("Singleton Service Registry", "Singleton Architectural Pattern", "class ServiceRegistry:")

    # Search: "DI Container architectural pattern"
    # Should match "Dependency Injection Container" with higher score than Singleton
    matches = engine.find_similar_patterns("DI Container architectural pattern")
    assert len(matches) == 2
    assert matches[0]["pattern_name"] == "Dependency Injection Container"
    assert matches[1]["pattern_name"] == "Singleton Service Registry"
    assert matches[0]["similarity_score"] > matches[1]["similarity_score"]
