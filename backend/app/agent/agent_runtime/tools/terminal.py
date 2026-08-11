"""
Terminal Tool — Real command execution for the agent.

Provides a ``run_command`` tool that executes shell commands in the workspace
with output capture, timeout enforcement, and working directory constraints.
"""

from __future__ import annotations

import os
import asyncio
import logging
import functools
from typing import Optional

from agent_runtime.tools import ToolDefinition, ToolResult, RiskLevel

logger = logging.getLogger("agent_runtime.tools.terminal")

# Maximum output size to prevent memory issues with runaway commands
_MAX_OUTPUT_BYTES = 100_000  # 100 KB


async def _run_command(
    command: str,
    workspace_root: str = ".",
    timeout: float = 60.0,
) -> ToolResult:
    """Execute a shell command in the workspace directory.

    Args:
        command: The command string to execute.
        workspace_root: Working directory for the command.
        timeout: Maximum execution time in seconds.

    Returns:
        ToolResult with combined stdout/stderr output.
    """
    # Security: reject obviously dangerous commands
    _dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){", "fork bomb"]
    cmd_lower = command.lower().strip()
    for d in _dangerous:
        if d in cmd_lower:
            return ToolResult(
                success=False,
                output="",
                error=f"Command rejected: contains dangerous pattern '{d}'",
            )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace_root,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout}s: {command}",
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]

        # Combine stdout and stderr for the agent to see
        output_parts = []
        if stdout.strip():
            output_parts.append(stdout.strip())
        if stderr.strip():
            output_parts.append(f"[stderr]\n{stderr.strip()}")

        output = "\n".join(output_parts) if output_parts else "(no output)"
        exit_code = proc.returncode or 0

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=f"Command exited with code {exit_code}" if exit_code != 0 else None,
            metadata={
                "command": command,
                "exit_code": exit_code,
                "stdout_bytes": len(stdout_bytes),
                "stderr_bytes": len(stderr_bytes),
            },
        )

    except Exception as e:
        logger.error("Failed to execute command '%s': %s", command, e)
        return ToolResult(
            success=False,
            output="",
            error=f"Failed to execute command: {type(e).__name__}: {e}",
        )


def create_terminal_tools(workspace_root: str, timeout: float = 60.0) -> list[ToolDefinition]:
    """Create terminal tools bound to a workspace root.

    Args:
        workspace_root: Working directory for command execution.
        timeout: Default timeout for commands.

    Returns:
        List of ToolDefinition objects ready for registry.
    """
    run = functools.partial(_run_command, workspace_root=workspace_root, timeout=timeout)

    return [
        ToolDefinition(
            name="run_command",
            description=(
                "Execute a shell command in the workspace directory. "
                "Use this to run tests, install dependencies, check git status, compile code, etc. "
                "Returns the combined stdout and stderr output."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                },
                "required": ["command"],
            },
            executor=run,
            risk_level=RiskLevel.HIGH,
            timeout=timeout,
        ),
    ]
