"""
Tool Registry — Manages tool registration, schemas, and execution.
"""

from __future__ import annotations

from typing import Any

from agent_os.tools.base import Tool


class ToolRegistry:
    """Registry of available tools with default mapping functions."""

    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance."""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Retrieve tool by name."""
        if isinstance(name, str) and "<|channel|>" in name:
            name = name.split("<|channel|>")[0]
        return self.tools.get(name)

    async def execute(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Execute tool by name and return a dictionary representation of the ToolResult."""
        tool = self.get(name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{name}' not found",
                "output": "",
            }

        result = await tool.execute(**kwargs)
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "metadata": result.metadata,
        }

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get schema definitions of all registered tools."""
        return [tool.to_schema() for tool in self.tools.values()]

    def create_default(self, workspace_root: str) -> ToolRegistry:
        """Helper to create and populate a registry with standard workspace tools."""
        from agent_os.tools.filesystem import EditFileTool, ReadFileTool, WriteFileTool
        from agent_os.tools.git import GitDiffTool, GitStatusTool
        from agent_os.tools.terminal import RunCommandTool

        self.register(ReadFileTool(workspace_root))
        self.register(WriteFileTool(workspace_root))
        self.register(EditFileTool(workspace_root))
        self.register(RunCommandTool(workspace_root))
        self.register(GitStatusTool(workspace_root))
        self.register(GitDiffTool(workspace_root))

        return self
