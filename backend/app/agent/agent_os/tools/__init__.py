"""
Tools Layer — Core contract, registry, and workspace implementations.
"""

from __future__ import annotations

from agent_os.tools.base import Tool, ToolResult
from agent_os.tools.registry import ToolRegistry
from agent_os.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool
from agent_os.tools.terminal import RunCommandTool
from agent_os.tools.git import GitStatusTool, GitDiffTool

__all__ = [
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "RunCommandTool",
    "GitStatusTool",
    "GitDiffTool",
]
