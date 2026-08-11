"""
Tests for file ownership validation (Phase 1c).

Ensures that agents cannot write files outside their allowed paths.
"""

import os
import pytest
from pathlib import Path

from agent_os.agent import (
    PathValidator,
    ToolValidator,
    ToolExecutor,
    ToolCall,
    ToolDefinition,
)


class TestPathValidator:
    """Test path validation for file ownership."""

    def test_empty_allowed_paths_allows_any(self):
        """Test that empty allowed_paths allows any path."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/any/file.txt", []
        )
        assert is_allowed

    def test_exact_path_match(self):
        """Test exact path matching."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/src/main.py", ["/workspace/src/main.py"]
        )
        assert is_allowed

    def test_directory_containment(self):
        """Test file is within allowed directory."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/src/module.py", ["/workspace/src"]
        )
        assert is_allowed

    def test_nested_directory_containment(self):
        """Test deeply nested file is within allowed directory."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/src/deep/nested/file.py", ["/workspace/src"]
        )
        assert is_allowed

    def test_path_outside_allowed(self):
        """Test path outside allowed paths is rejected."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/reports/data.md", ["/workspace/src"]
        )
        assert not is_allowed
        assert "PATH_NOT_ALLOWED" in error

    def test_multiple_allowed_paths(self):
        """Test matching against multiple allowed paths."""
        allowed = ["/workspace/src", "/workspace/tests"]
        
        # Should pass for src
        is_allowed, _ = PathValidator.is_within_allowed_paths(
            "/workspace/src/main.py", allowed
        )
        assert is_allowed
        
        # Should pass for tests
        is_allowed, _ = PathValidator.is_within_allowed_paths(
            "/workspace/tests/test_main.py", allowed
        )
        assert is_allowed
        
        # Should fail for docs
        is_allowed, _ = PathValidator.is_within_allowed_paths(
            "/workspace/docs/README.md", allowed
        )
        assert not is_allowed

    def test_wildcard_pattern(self):
        """Test wildcard pattern matching."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/tests/test_foo.py", ["/workspace/tests/*.py"]
        )
        assert is_allowed

    def test_wildcard_not_matching(self):
        """Test wildcard pattern not matching."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/src/main.py", ["/workspace/tests/*.py"]
        )
        assert not is_allowed

    def test_forbidden_git_directory(self):
        """Test .git directory is forbidden."""
        is_safe, error = PathValidator.validate_write_safety(
            "/workspace/.git/config", ["/workspace"]
        )
        assert not is_safe
        assert "FORBIDDEN_PATH" in error

    def test_forbidden_env_file(self):
        """Test .env file is forbidden."""
        is_safe, error = PathValidator.validate_write_safety(
            "/workspace/.env", ["/workspace"]
        )
        assert not is_safe
        assert "FORBIDDEN_PATH" in error

    def test_forbidden_secrets(self):
        """Test secrets file is forbidden."""
        is_safe, error = PathValidator.validate_write_safety(
            "/workspace/secrets.key", ["/workspace"]
        )
        assert not is_safe
        assert "FORBIDDEN_PATH" in error

    def test_allowed_file_not_forbidden(self):
        """Test allowed file is not marked forbidden."""
        is_safe, error = PathValidator.validate_write_safety(
            "/workspace/src/main.py", ["/workspace/src"]
        )
        assert is_safe

    def test_relative_path_with_workspace_root(self):
        """Test relative path resolution with workspace root."""
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "src/main.py", ["src"], workspace_root="/workspace"
        )
        assert is_allowed

    def test_normalize_path_removes_dots(self):
        """Test path normalization."""
        normalized = PathValidator.normalize_path("/workspace/./src/../src/./main.py")
        assert ".." not in normalized
        assert "/src" in normalized


class TestToolValidator:
    """Test tool validation with path checking."""

    @pytest.mark.asyncio
    async def test_write_file_validation_allowed(self):
        """Test write_file is allowed to write within allowed_paths."""
        validator = ToolValidator()

        tool_def = ToolDefinition(
            name="write_file",
            description="Write file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            executor=None,
        )

        tool_call = ToolCall(
            tool_name="write_file",
            arguments={"path": "/workspace/src/main.py", "content": "code"},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        assert is_valid

    @pytest.mark.asyncio
    async def test_write_file_validation_forbidden(self):
        """Test write_file rejects writes outside allowed_paths."""
        validator = ToolValidator()

        tool_def = ToolDefinition(
            name="write_file",
            description="Write file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            executor=None,
        )

        tool_call = ToolCall(
            tool_name="write_file",
            arguments={"path": "/workspace/RESEARCH_REPORT.md", "content": "data"},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        assert not is_valid
        assert "PATH_NOT_ALLOWED" in error

    @pytest.mark.asyncio
    async def test_write_file_to_forbidden_git(self):
        """Test write_file rejects writes to .git directory."""
        validator = ToolValidator()

        tool_def = ToolDefinition(
            name="write_file",
            description="Write file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            executor=None,
        )

        tool_call = ToolCall(
            tool_name="write_file",
            arguments={"path": "/workspace/.git/HEAD", "content": "ref: refs/heads/main"},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace"]
        )
        assert not is_valid
        assert "FORBIDDEN_PATH" in error

    @pytest.mark.asyncio
    async def test_create_file_validation(self):
        """Test create_file validation."""
        validator = ToolValidator()

        tool_def = ToolDefinition(
            name="create_file",
            description="Create file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path"],
            },
            executor=None,
        )

        # Allowed path
        tool_call = ToolCall(
            tool_name="create_file",
            arguments={"path": "/workspace/src/new_file.py"},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        assert is_valid

        # Forbidden path
        tool_call = ToolCall(
            tool_name="create_file",
            arguments={"path": "/workspace/forbidden/file.py"},
            tool_call_id="call-2",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        assert not is_valid

    @pytest.mark.asyncio
    async def test_rename_file_validation(self):
        """Test rename_file validates both old and new paths."""
        validator = ToolValidator()

        tool_def = ToolDefinition(
            name="rename_file",
            description="Rename file",
            input_schema={
                "type": "object",
                "properties": {
                    "old_path": {"type": "string"},
                    "new_path": {"type": "string"},
                },
                "required": ["old_path", "new_path"],
            },
            executor=None,
        )

        # Both paths allowed
        tool_call = ToolCall(
            tool_name="rename_file",
            arguments={
                "old_path": "/workspace/src/old.py",
                "new_path": "/workspace/src/new.py",
            },
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        assert is_valid

        # New path not allowed (trying to escape)
        tool_call = ToolCall(
            tool_name="rename_file",
            arguments={
                "old_path": "/workspace/src/file.py",
                "new_path": "/workspace/escape.py",
            },
            tool_call_id="call-2",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        assert not is_valid

    @pytest.mark.asyncio
    async def test_read_file_not_restricted(self):
        """Test that read_file is not restricted by allowed_paths."""
        validator = ToolValidator()

        tool_def = ToolDefinition(
            name="read_file",
            description="Read file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
            executor=None,
        )

        # Can read outside allowed paths (read-only is safer)
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/workspace/docs/README.md"},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace/src"]
        )
        # Read operations are not restricted
        assert is_valid


class TestTaskPathValidation:
    """Test Task validation of allowed_paths."""

    def test_task_with_allowed_paths(self):
        """Test task with valid allowed_paths."""
        from agent_os.agent import Task

        task = Task(
            task_id="t1",
            title="Test",
            description="Test task",
            agent_type="coding",
            allowed_paths=["/workspace/src", "/workspace/tests"],
        )

        is_valid, errors = task.validate_paths()
        assert is_valid
        assert len(errors) == 0

    def test_task_with_empty_allowed_paths(self):
        """Test task with no allowed_paths raises error."""
        from agent_os.agent import Task

        task = Task(
            task_id="t1",
            title="Test",
            description="Test task",
            agent_type="coding",
            allowed_paths=[],
        )

        is_valid, errors = task.validate_paths()
        assert not is_valid
        assert len(errors) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
