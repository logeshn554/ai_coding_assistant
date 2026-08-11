"""
Tests for the comprehensive tool system.
"""

import asyncio
import os
import tempfile
import pytest
from pathlib import Path

from agent_os.agent import (
    ToolRegistry,
    ToolValidator,
    ToolExecutor,
    ToolCall,
    PathValidator,
)


class TestToolRegistry:
    """Test tool registry functionality."""

    def test_registry_creation(self):
        """Test that registry creates with default tools."""
        registry = ToolRegistry()
        tools = registry.get_all()

        # Should have at least 20 tools
        assert len(tools) >= 20

    def test_get_tool(self):
        """Test getting a specific tool."""
        registry = ToolRegistry()

        tool = registry.get("read_file")
        assert tool is not None
        assert tool.name == "read_file"
        assert tool.description == "Read file contents"

    def test_tool_list(self):
        """Test listing all tools."""
        registry = ToolRegistry()
        tools_list = registry.list_tools()

        assert len(tools_list) >= 20
        assert all("name" in t for t in tools_list)
        assert all("description" in t for t in tools_list)


class TestPathValidator:
    """Test path validation for file ownership."""

    def test_path_within_allowed(self):
        """Test path is within allowed paths."""
        allowed = ["/workspace/src"]
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/src/main.py", allowed
        )
        assert is_allowed

    def test_path_outside_allowed(self):
        """Test path outside allowed paths."""
        allowed = ["/workspace/src"]
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "/workspace/reports/data.md", allowed
        )
        assert not is_allowed
        assert "PATH_NOT_ALLOWED" in error

    def test_wildcard_pattern(self):
        """Test wildcard pattern matching."""
        allowed = ["tests/*.py"]
        is_allowed, error = PathValidator.is_within_allowed_paths(
            "tests/test_foo.py", allowed
        )
        assert is_allowed


class TestToolValidator:
    """Test tool validation."""

    @pytest.mark.asyncio
    async def test_schema_validation(self):
        """Test schema validation."""
        validator = ToolValidator()

        from agent_os.agent import ToolDefinition
        tool_def = ToolDefinition(
            name="test_tool",
            description="Test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["name"],
            },
            executor=None,
        )

        # Valid call
        tool_call = ToolCall(
            tool_name="test_tool",
            arguments={"name": "test", "count": 5},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(tool_call, tool_def, [])
        assert is_valid

    @pytest.mark.asyncio
    async def test_missing_required_field(self):
        """Test missing required field."""
        validator = ToolValidator()

        from agent_os.agent import ToolDefinition
        tool_def = ToolDefinition(
            name="test_tool",
            description="Test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
            executor=None,
        )

        # Missing required field
        tool_call = ToolCall(
            tool_name="test_tool",
            arguments={},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(tool_call, tool_def, [])
        assert not is_valid
        assert "Missing required field" in error

    @pytest.mark.asyncio
    async def test_path_validation_in_tool_call(self):
        """Test path validation during tool validation."""
        validator = ToolValidator()

        from agent_os.agent import ToolDefinition
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

        # Path outside allowed
        tool_call = ToolCall(
            tool_name="write_file",
            arguments={"path": "/forbidden/file.txt", "content": "data"},
            tool_call_id="call-1",
        )

        is_valid, error = await validator.validate(
            tool_call, tool_def, ["/workspace"]
        )
        assert not is_valid
        assert "PATH_NOT_ALLOWED" in error


class TestFileTools:
    """Test file tool operations."""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self):
        """Test writing and reading a file."""
        from agent_os.agent.tool_registry import FileTools

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            content = "Hello, World!"

            # Write file
            result = await FileTools.write_file(file_path, content)
            assert "successfully" in result.lower()

            # Read file
            read_content = await FileTools.read_file(file_path)
            assert read_content == content

    @pytest.mark.asyncio
    async def test_create_file(self):
        """Test creating a file."""
        from agent_os.agent.tool_registry import FileTools

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "new_file.txt")

            result = await FileTools.create_file(file_path, "content")
            assert "successfully" in result.lower()
            assert os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_edit_file(self):
        """Test editing a file."""
        from agent_os.agent.tool_registry import FileTools

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            await FileTools.write_file(file_path, "Hello World")

            # Edit file
            result = await FileTools.edit_file(file_path, "World", "Python")
            assert "successfully" in result.lower()

            # Verify
            content = await FileTools.read_file(file_path)
            assert "Hello Python" in content

    @pytest.mark.asyncio
    async def test_delete_file(self):
        """Test deleting a file."""
        from agent_os.agent.tool_registry import FileTools

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            await FileTools.write_file(file_path, "content")

            result = await FileTools.delete_file(file_path)
            assert "deleted" in result.lower()
            assert not os.path.exists(file_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
