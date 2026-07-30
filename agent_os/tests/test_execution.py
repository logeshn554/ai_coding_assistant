import os
import tempfile
import pytest
from agent_os.execution.engine import (
    TransactionalExecutionEngine,
    MergeConflictError,
    PatchSyntaxError,
    TransactionError
)

def test_execution_engine_successful_transaction():
    engine = TransactionalExecutionEngine()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.py")
        original_code = """def calc(x):
    return x * 2
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        # 1. Begin transaction
        tx = engine.create_transaction()
        tx.begin()

        # 2. Apply valid patch
        tx.apply_patch(
            file_path=file_path,
            target_content="return x * 2",
            replacement_content="return x * 3"
        )

        # 3. Verify file on disk is NOT updated yet (Never write directly)
        with open(file_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        assert disk_content == original_code

        # 4. Commit transaction
        tx.commit()

        # 5. Verify file on disk IS updated
        with open(file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()
        assert "return x * 3" in updated_content

def test_execution_engine_reject_broken_syntax():
    engine = TransactionalExecutionEngine()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "app.py")
        original_code = """def start():
    print("starting")
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        tx = engine.create_transaction()
        tx.begin()

        # Try to apply patch with invalid Python syntax
        with pytest.raises(PatchSyntaxError):
            tx.apply_patch(
                file_path=file_path,
                target_content='print("starting")',
                replacement_content='print("starting" - broken_syntax = :'
            )

        tx.rollback()

        # Verify app.py remains completely original
        with open(file_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        assert disk_content == original_code

def test_execution_engine_conflict_detection():
    engine = TransactionalExecutionEngine()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "helper.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("def helper():\n    pass")

        tx = engine.create_transaction()
        tx.begin()

        # Try to replace text that does not exist in helper.py
        with pytest.raises(MergeConflictError):
            tx.apply_patch(
                file_path=file_path,
                target_content="def non_existent_function():",
                replacement_content="def renamed():"
            )
        tx.rollback()

def test_execution_engine_rollback():
    engine = TransactionalExecutionEngine()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "db.py")
        original_code = "def query_db():\n    return []"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        tx = engine.create_transaction()
        tx.begin()
        tx.apply_patch(
            file_path=file_path,
            target_content="return []",
            replacement_content="return ['user1']"
        )

        # Rollback instead of commit
        tx.rollback()

        # File must remain original
        with open(file_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        assert disk_content == original_code
