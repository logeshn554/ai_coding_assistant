"""
Terminal Tool — Real command execution for the agent.

Provides a ``run_command`` tool that executes shell commands in the workspace
with output capture, timeout enforcement, and working directory constraints.
"""

from __future__ import annotations

import functools
import logging
import os

from agent_runtime.tools import RiskLevel, ToolDefinition, ToolResult

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
        from backend.app.tools.terminal_tool import run_shell_command

        class DummySession:
            def __init__(self, root: str):
                self.workspace_root = os.path.abspath(root)
            async def send_ws_message(self, msg: dict):
                pass

        session = DummySession(workspace_root)
        out = await run_shell_command(session, command, timeout_seconds=int(timeout))
        is_error = "Failed to execute command:" in out or "Command timed out" in out
        return ToolResult(
            success=not is_error,
            output=out,
            error=out if is_error else None,
            metadata={"command": command},
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
