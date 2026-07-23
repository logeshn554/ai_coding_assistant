"""Terminal / shell execution helpers for agent tool dispatch."""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from typing import Any, Dict


async def run_shell_command(session: Any, command: str) -> str:
    """Run a shell command asynchronously and stream combined stdout/stderr.

    Enforces a workspace-root ``cd`` lock and a hard 30-second timeout.

    Args:
        session: Active AgentSession (workspace_root, send_ws_message).
        command: Shell command string to execute.

    Returns:
        Combined command output, or a failure/timeout message.
    """
    # Working directory lock: prevent escaping the workspace root via any cd form.
    # Catches: cd .., cd ../../, cd /etc, cd $HOME, cd C:\Windows, etc.
    _cd_match = re.search(r'(?:^|[;&|])\s*cd\s+(\S+)', command)
    if _cd_match:
        _target = _cd_match.group(1).strip().strip('"\'')
        # Always block .. traversal
        if ".." in _target:
            return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."
        # Block absolute paths that are clearly outside the workspace
        _abs_target = os.path.abspath(os.path.join(session.workspace_root, _target)) if not os.path.isabs(_target) else os.path.abspath(_target)
        _ws_real = os.path.realpath(session.workspace_root)
        if not _abs_target.startswith(_ws_real):
            return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."
    elif "cd .." in command or "cd/" in command:
        return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."

    from ..shell_adapter import ShellAdapter
    shell_executable = ShellAdapter.get_shell_executable(interactive=False)

    kwargs: Dict[str, Any] = {}
    if sys.platform == "win32":
        import subprocess
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        import pwd
        def drop_privileges():
            try:
                nobody = pwd.getpwnam('nobody')
                os.setgid(nobody.pw_gid)
                os.setuid(nobody.pw_uid)
            except Exception:
                pass
        kwargs["preexec_fn"] = drop_privileges

    start_time = time.time()

    # Send initial execution state
    await session.send_ws_message({
        "type": "terminal_status",
        "status": "running",
        "command": command
    })
    await session.send_ws_message({
        "type": "terminal_stream",
        "content": f"\r\n\x1b[35m[DevPilot Agent]\x1b[0m $ {command}\r\n"
    })

    try:
        process = await asyncio.create_subprocess_exec(
            *shell_executable,
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=session.workspace_root,
            **kwargs
        )

        from ..processes import confine_subprocess
        try:
            confine_subprocess(process.pid)
        except Exception:
            pass

        output_chunks = []
        while True:
            elapsed = time.time() - start_time
            remaining = 30.0 - elapsed
            if remaining <= 0:
                raise asyncio.TimeoutError()

            try:
                line_bytes = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
            except asyncio.TimeoutError:
                raise

            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace")
            output_chunks.append(line)

            # Stream terminal line to client
            await session.send_ws_message({
                "type": "terminal_stream",
                "content": line
            })

        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=max(1.0, 30.0 - (time.time() - start_time)))
        except asyncio.TimeoutError:
            raise
        elapsed_time = round(time.time() - start_time, 2)

        # Send terminal finished status
        await session.send_ws_message({
            "type": "terminal_status",
            "status": "completed",
            "exit_code": exit_code,
            "elapsed": elapsed_time
        })

        output = "".join(output_chunks)
        return output if output.strip() else "[Command executed with no output]"
    except asyncio.TimeoutError:
        elapsed_time = round(time.time() - start_time, 2)
        try:
            if sys.platform == "win32":
                import subprocess
                subprocess.call(f"taskkill /F /T /PID {process.pid}", shell=True)
            else:
                process.kill()
            # Reap the child process to release the stdout pipe fd.
            # asyncio.shield ensures the wait is not cancelled by outer cancellation.
            await asyncio.shield(process.wait())
        except Exception:
            pass
        await session.send_ws_message({
            "type": "terminal_status",
            "status": "failed",
            "exit_code": -1,
            "elapsed": elapsed_time
        })
        return "Failed to execute command: Command timed out after 30 seconds."
    except Exception as e:
        elapsed_time = round(time.time() - start_time, 2)
        await session.send_ws_message({
            "type": "terminal_status",
            "status": "failed",
            "exit_code": -1,
            "elapsed": elapsed_time
        })
        return f"Failed to execute command: {str(e)}"


async def run_terminal_command(
    session: Any,
    tc_id: str,
    args: Dict[str, Any],
    auto_apply: bool,
) -> str:
    """Execute run_terminal_command with permission-manager guardrails.

    Args:
        session: Active AgentSession (permissions, confirmations, audit).
        tc_id: Tool call identifier for confirmation correlation.
        args: Tool arguments; uses ``command``.
        auto_apply: Unused for terminal (permissions still apply); kept for API parity.

    Returns:
        Command output or a cancellation/timeout message.
    """
    cmd = args.get("command", "")
    name = "run_terminal_command"

    is_approved = False
    risk = "mutative"
    reason = ""

    if session.permission_manager:
        is_approved, risk, reason = session.permission_manager.check_permission(cmd)

    # If not auto-approved, request permission via popup dialog
    if not is_approved:
        event = asyncio.Event()
        session.pending_confirmations[tc_id] = {
            "event": event,
            "approved": False,
            "scope": "once",
            "command": cmd
        }

        explanation = f"Runs the terminal command: `{cmd}`"

        await session.send_ws_message({
            "type": "permission_request",
            "tool_call_id": tc_id,
            "tool_name": name,
            "command": cmd,
            "risk": risk,
            "reason": reason,
            "explanation": explanation,
            "args": args
        })

        try:
            await asyncio.wait_for(event.wait(), timeout=300)
        except asyncio.TimeoutError:
            session.pending_confirmations.pop(tc_id, None)
            session.log_audit(name, args, "timeout", "Confirmation timed out — client disconnected.")
            return "Action timed out: client did not respond within 5 minutes."
        decision = session.pending_confirmations[tc_id]
        del session.pending_confirmations[tc_id]

        if not decision["approved"]:
            session.log_audit(name, args, "rejected", "User rejected command execution.")
            return "Action cancelled by the user."

        # Extract potentially edited command and scope
        cmd = decision.get("command", cmd)
        scope = decision.get("scope", "once")

        # Grant permission if session/project level was chosen
        if scope in ("session", "project") and session.permission_manager:
            session.permission_manager.grant_permission(cmd, scope)

    # Execute command
    session.log_audit(name, args, "pending", f"Running command: {cmd}")
    result = await run_shell_command(session, cmd)
    session.log_audit(name, args, "success", f"Command stdout returned: {len(result)} bytes")
    return result
