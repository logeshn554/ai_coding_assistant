"""
Terminal Tool — Runs terminal commands safely in the workspace.
"""

from __future__ import annotations

import asyncio
import shlex
import subprocess
from typing import Any

from agent_os.tools.base import Tool, ToolResult


class RunCommandTool(Tool):
    """Execute a shell command inside the workspace directory, restricted to allowed commands."""

    def __init__(self, workspace_root: str, timeout: float = 120.0) -> None:
        self.workspace_root = workspace_root
        self.timeout = timeout
        self.allowed_commands = {
            "python", "pip", "pytest", "npm", "yarn", "git",
            "ls", "cat", "grep", "find", "head", "tail",
            "go", "cargo", "make", "docker", "node",
        }

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return "Execute a shell command in the workspace (with safety restrictions)."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run",
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, **kwargs: Any) -> ToolResult:
        try:
            # Parse command arguments securely using shlex
            parts = shlex.split(command)
            if not parts:
                return ToolResult(
                    success=False,
                    output="",
                    error="Command string is empty",
                )

            # Security: check base command against whitelist
            base_cmd = parts[0].split("/")[-1].split("\\")[-1]  # Get base executable name
            if base_cmd not in self.allowed_commands:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command '{base_cmd}' not allowed. Allowed: {', '.join(sorted(self.allowed_commands))}",
                )

            # Execute command using subprocess
            proc = await asyncio.create_subprocess_exec(
                *parts,
                cwd=self.workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {self.timeout}s",
                )

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            return ToolResult(
                success=proc.returncode == 0,
                output=output,
                error=error if error else None,
                metadata={
                    "exit_code": proc.returncode,
                    "command": command,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing command: {e}",
            )
