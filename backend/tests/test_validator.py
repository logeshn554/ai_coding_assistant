"""Tests for Phase 8 — Validator."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from app.agent.validator import Validator


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with some files."""
    return tmp_path


class TestValidator:
    def test_valid_python_file(self, workspace):
        fpath = workspace / "main.py"
        fpath.write_text("def main():\n    return 42\n")

        v = Validator(str(workspace))
        result = v.validate(files_written=["main.py"])

        assert result.passed
        assert any("main.py" in c for c in result.passed_checks)

    def test_syntax_error_detected(self, workspace):
        fpath = workspace / "broken.py"
        fpath.write_text("def broken(\n    # unclosed paren\n")

        v = Validator(str(workspace))
        result = v.validate(files_written=["broken.py"])

        assert not result.passed
        assert any("SyntaxError" in f for f in result.failures)

    def test_missing_file_detected(self, workspace):
        v = Validator(str(workspace))
        result = v.validate(files_written=["nonexistent.py"])

        assert not result.passed
        assert any("nonexistent.py" in f for f in result.failures)

    def test_empty_file_warning(self, workspace):
        fpath = workspace / "empty.py"
        fpath.write_bytes(b"")

        v = Validator(str(workspace))
        result = v.validate(files_written=["empty.py"])

        # Empty file should warn (file exists but is 0 bytes)
        assert any("empty.py" in w for w in result.warnings) or not result.passed

    def test_plan_required_file_not_created(self, workspace):
        v = Validator(str(workspace))
        result = v.validate(
            files_written=[],
            files_to_create=["should_exist.py"],
        )
        assert not result.passed
        assert any("should_exist.py" in f for f in result.failures)

    def test_multiple_python_files(self, workspace):
        (workspace / "a.py").write_text("x = 1\n")
        (workspace / "b.py").write_text("y = 2\n")

        v = Validator(str(workspace))
        result = v.validate(files_written=["a.py", "b.py"])

        assert result.passed
        assert result.checks_run >= 2

    def test_no_workspace(self):
        v = Validator("")
        result = v.validate(files_written=["anything.py"])
        assert len(result.warnings) > 0  # Should warn about no workspace

    def test_to_prompt_block_on_failure(self, workspace):
        v = Validator(str(workspace))
        result = v.validate(files_written=["missing.py"])

        block = result.to_prompt_block()
        assert "FAIL" in block
        assert "missing.py" in block

    def test_to_summary(self, workspace):
        fpath = workspace / "ok.py"
        fpath.write_text("print('ok')\n")

        v = Validator(str(workspace))
        result = v.validate(files_written=["ok.py"])
        summary = result.to_summary()
        assert "Validation:" in summary

    def test_typescript_file_passes(self, workspace):
        fpath = workspace / "app.ts"
        fpath.write_text("export const greet = (name: string) => `Hello ${name}`;\n")

        v = Validator(str(workspace))
        result = v.validate(files_written=["app.ts"])
        assert result.checks_run > 0
