"""
Git Tools — Implements real git status and git diff tool executions.
"""

from __future__ import annotations

import subprocess
from typing import Any

from agent_os.tools.base import Tool, ToolResult


class GitDiffTool(Tool):
    """Retrieves unified git diff from the workspace."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "Get unified diff of all uncommitted changes."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", "diff"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting git diff: {e}",
            )


class GitStatusTool(Tool):
    """Retrieves git repository status (short format)."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Get git repository status."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting git status: {e}",
            )
