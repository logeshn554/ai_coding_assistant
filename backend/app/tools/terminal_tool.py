"""Terminal / shell execution helpers for agent tool dispatch."""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from typing import Any, Dict

# A2: Pattern-matched long-running command allowlist (seconds)
_LONG_RUNNING_PATTERNS: list = [
    (re.compile(r'\b(npm|yarn|pnpm)\s+(install|ci|i)\b'), 180),
    (re.compile(r'\bpip\s+install\b'), 180),
    (re.compile(r'\bcargo\s+build\b'), 180),
    (re.compile(r'\bnpm\s+run\s+build\b'), 120),
    (re.compile(r'\bnpm\s+(run\s+)?test\b'), 120),
    (re.compile(r'\bpytest\b'), 120),
    (re.compile(r'\bmvn\b'), 120),
    (re.compile(r'\bgradle\b'), 120),
]
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 300


def _resolve_timeout(command: str, explicit_timeout: int | None = None) -> float:
    """A2: Return the appropriate timeout for *command* in seconds."""
    if explicit_timeout is not None:
        return float(min(explicit_timeout, _MAX_TIMEOUT))
    for pattern, seconds in _LONG_RUNNING_PATTERNS:
        if pattern.search(command):
            return float(seconds)
    return float(_DEFAULT_TIMEOUT)


async def run_shell_command(session: Any, command: str, timeout_seconds: int | None = None) -> str:
    """Run a shell command asynchronously and stream combined stdout/stderr.

    Enforces a workspace-root ``cd`` lock and a dynamic timeout (A2).
    Sets stdin=DEVNULL and CI=true to prevent interactive prompts (A3).

    Args:
        session: Active AgentSession (workspace_root, send_ws_message).
        command: Shell command string to execute.
        timeout_seconds: Optional override; capped at 300 s.

    Returns:
        Combined command output (partial on timeout), or a failure message.
    """
    # Working directory lock (Bug 6: handle command chaining and absolute paths)
    current_dir = os.path.realpath(session.workspace_root)
    sub_commands = re.split(r'[;&|]+', command)
    for sub_cmd in sub_commands:
        sub_cmd = sub_cmd.strip()
        cd_match = re.match(r'^cd\b\s*(.*)', sub_cmd) or re.match(r'^cd(\..*)', sub_cmd)
        if cd_match:
            target = cd_match.group(1).strip().strip('"\'')
            if not target or target == "~":
                target = session.workspace_root
            if not os.path.isabs(target):
                target = os.path.join(current_dir, target)
            target = os.path.abspath(target)
            real_target = os.path.realpath(target)
            if not real_target.startswith(os.path.realpath(session.workspace_root)):
                return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."
            current_dir = real_target
        elif "cd .." in sub_cmd or "cd/" in sub_cmd or re.search(r'\bcd\b.*\.\.', sub_cmd):
            return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."

    from ..shell_adapter import ShellAdapter
    shell_executable = ShellAdapter.get_shell_executable(interactive=False)

    # A2: resolve dynamic timeout
    timeout = _resolve_timeout(command, timeout_seconds)

    # A3: build environment with CI flags so scaffolding tools skip prompts
    env = os.environ.copy()
    env["CI"] = "true"
    env["npm_config_yes"] = "true"

    kwargs: Dict[str, Any] = {
        "stdin": asyncio.subprocess.DEVNULL,  # A3: never read from parent stdin
        "env": env,
    }
    if sys.platform == "win32":
        import subprocess
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    start_time = time.time()

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
            remaining = timeout - elapsed
            if remaining <= 0:
                raise asyncio.TimeoutError()

            try:
                line_bytes = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
            except asyncio.TimeoutError:
                raise

            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace")
            clean_line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', line).replace('\x03', '')
            output_chunks.append(clean_line)

            try:
                from .server_watcher import global_server_watcher
                global_server_watcher.check_log_line(clean_line, session)
            except Exception:
                pass

            await session.send_ws_message({
                "type": "terminal_stream",
                "content": clean_line
            })

        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=max(1.0, timeout - (time.time() - start_time)))
        except asyncio.TimeoutError:
            raise
        elapsed_time = round(time.time() - start_time, 2)

        await session.send_ws_message({
            "type": "terminal_status",
            "status": "completed",
            "exit_code": exit_code,
            "elapsed": elapsed_time
        })
        try:
            session.last_exit_code = exit_code
        except Exception:
            pass

        output = "".join(output_chunks)
        return output if output.strip() else "[Command executed with no output]"

    except asyncio.TimeoutError:
        elapsed_time = round(time.time() - start_time, 2)
        # A2: collect any partial output already buffered
        partial = "".join(output_chunks).strip()
        try:
            if sys.platform == "win32":
                import subprocess
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(process.pid)])
            else:
                process.kill()
            await asyncio.shield(process.wait())
        except Exception:
            pass
        await session.send_ws_message({
            "type": "terminal_status",
            "status": "failed",
            "exit_code": -1,
            "elapsed": elapsed_time
        })
        try:
            session.last_exit_code = -1
        except Exception:
            pass
        timeout_msg = f"Failed to execute command: Command timed out after {timeout:.0f} seconds."
        if partial:
            return f"{timeout_msg}\n\nPartial output before timeout:\n{partial}"
        return timeout_msg

    except Exception as e:
        elapsed_time = round(time.time() - start_time, 2)
        await session.send_ws_message({
            "type": "terminal_status",
            "status": "failed",
            "exit_code": -1,
            "elapsed": elapsed_time
        })
        try:
            session.last_exit_code = -1
        except Exception:
            pass
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
        args: Tool arguments; uses ``command`` and optional ``timeout_seconds``.
        auto_apply: Unused for terminal (permissions still apply); kept for API parity.

    Returns:
        Command output or a cancellation/timeout message.
    """
    cmd = args.get("command", "")
    # A2: support agent-supplied timeout override
    explicit_timeout = args.get("timeout_seconds", None)
    if explicit_timeout is not None:
        try:
            explicit_timeout = int(explicit_timeout)
        except (TypeError, ValueError):
            explicit_timeout = None
    name = "run_terminal_command"

    is_approved = False
    risk = "mutative"
    reason = ""

    if session.permission_manager:
        is_approved, risk, reason = session.permission_manager.check_permission(cmd)

    # If auto_apply is set, treat non-destructive commands as approved
    if not is_approved and auto_apply and risk != "destructive":
        is_approved = True

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

        cmd = decision.get("command", cmd)
        scope = decision.get("scope", "once")

        if scope in ("session", "project") and session.permission_manager:
            session.permission_manager.grant_permission(cmd, scope)

    # Execute command
    session.log_audit(name, args, "pending", f"Running command: {cmd}")
    try:
        session.last_exit_code = 0
    except Exception:
        pass
    result = await run_shell_command(session, cmd, timeout_seconds=explicit_timeout)
    session.log_audit(name, args, "success", f"Command stdout returned: {len(result)} bytes")

    exit_code = getattr(session, "last_exit_code", 0)
    if exit_code != 0:
        if hasattr(session, "_run_llm_query"):
            import json
            import logging
            import uuid
            logger = logging.getLogger("app.tools.terminal_tool")
            
            await session.send_ws_message({
                "type": "status",
                "status": "thinking",
                "message": f"Terminal Agent: Diagnosing command failure (exit code {exit_code})..."
            })
            
            prompt = (
                f"The terminal command `{cmd}` failed with exit status {exit_code}. Here is the output:\n"
                f"{result[-2000:]}\n\n"
                "Analyze the command and output to determine the root cause of the error. Propose a fix.\n"
                "If the fix is a shell command that can be executed to resolve the issue (e.g. running 'npm install <package>', 'pip install <package>', 'npm install', or similar setup commands), set 'can_auto_fix' to true and provide the 'fix_command'.\n"
                "Output your response strictly as a JSON object:\n"
                "{\n"
                "  \"root_cause\": \"A clear explanation of why the command failed\",\n"
                "  \"fix_suggestion\": \"What needs to be done to fix it\",\n"
                "  \"fix_command\": \"Optional shell command to execute the fix\",\n"
                "  \"can_auto_fix\": true\n"
                "}\n"
                "Respond with ONLY the JSON object, no other text."
            )
            system_prompt = "You are a senior DevOps and codebase recovery expert. Analyze the failure and output diagnostics JSON."
            
            try:
                response = await session._run_llm_query(system_prompt, prompt)
                clean_res = response.strip()
                if clean_res.startswith("```json"):
                    clean_res = clean_res[7:]
                if clean_res.endswith("```"):
                    clean_res = clean_res[:-3]
                
                parsed = json.loads(clean_res.strip())
                root_cause = parsed.get("root_cause", "Unknown error")
                fix_suggestion = parsed.get("fix_suggestion", "Inspect logs and configure correctly")
                fix_command = parsed.get("fix_command")
                can_auto_fix = parsed.get("can_auto_fix", False)
                
                await session.send_ws_message({
                    "type": "text_delta",
                    "content": f"\n\n### 🛠️ Terminal Diagnosis\n* **Root Cause:** {root_cause}\n* **Suggestion:** {fix_suggestion}\n"
                })
                
                if can_auto_fix and fix_command:
                    await session.send_ws_message({
                        "type": "text_delta",
                        "content": f"Attempting automatic recovery: Running `{fix_command}`...\n"
                    })
                    
                    is_approved = False
                    risk = "mutative"
                    reason = "Terminal Agent automatic fix execution"
                    if session.permission_manager:
                        is_approved, risk, reason = session.permission_manager.check_permission(fix_command)
                        
                    if not is_approved:
                        fix_tc_id = f"fix_{uuid.uuid4().hex[:6]}"
                        event = asyncio.Event()
                        session.pending_confirmations[fix_tc_id] = {
                            "event": event,
                            "approved": False,
                            "scope": "once",
                            "command": fix_command
                        }
                        
                        await session.send_ws_message({
                            "type": "permission_request",
                            "tool_call_id": fix_tc_id,
                            "tool_name": "run_terminal_command",
                            "command": fix_command,
                            "risk": risk,
                            "reason": reason,
                            "explanation": f"Terminal Agent wants to run fix command: `{fix_command}`",
                            "args": {"command": fix_command}
                        })
                        
                        try:
                            await asyncio.wait_for(event.wait(), timeout=300)
                        except asyncio.TimeoutError:
                            session.pending_confirmations.pop(fix_tc_id, None)
                            await session.send_ws_message({"type": "text_delta", "content": "*Fix command permission check timed out.*\n"})
                            return result
                            
                        decision = session.pending_confirmations[fix_tc_id]
                        del session.pending_confirmations[fix_tc_id]
                        
                        if not decision["approved"]:
                            await session.send_ws_message({
                                "type": "text_delta",
                                "content": "*Automatic recovery cancelled by user.*\n"
                            })
                            return result
                        fix_command = decision.get("command", fix_command)
                    
                    await session.send_ws_message({
                        "type": "status",
                        "status": "tool_executing",
                        "message": f"Executing fix command: `{fix_command}`..."
                    })
                    
                    fix_result = await run_shell_command(session, fix_command)
                    await session.send_ws_message({
                        "type": "text_delta",
                        "content": f"Fix command finished. Output:\n```\n{fix_result[:500]}...\n```\n"
                    })
                    
                    await session.send_ws_message({
                        "type": "text_delta",
                        "content": f"Retrying original command: `{cmd}`\n"
                    })
                    try:
                        session.last_exit_code = 0
                    except Exception:
                        pass
                    result = await run_shell_command(session, cmd, timeout_seconds=explicit_timeout)
                    session.log_audit(name, args, "success", f"Retried command stdout returned: {len(result)} bytes")
            except Exception as e:
                logger.error(f"Failed during self-healing terminal execution: {str(e)}")

    return result


async def run_shell_command_silent(session: Any, command: str, timeout_seconds: int | None = None) -> str:
    """Run a shell command silently in the background, without sending websocket updates or checking permissions."""
    # Working directory lock (Bug 6: handle command chaining and absolute paths)
    current_dir = os.path.realpath(session.workspace_root)
    sub_commands = re.split(r'[;&|]+', command)
    for sub_cmd in sub_commands:
        sub_cmd = sub_cmd.strip()
        cd_match = re.match(r'^cd\b\s*(.*)', sub_cmd) or re.match(r'^cd(\..*)', sub_cmd)
        if cd_match:
            target = cd_match.group(1).strip().strip('"\'')
            if not target or target == "~":
                target = session.workspace_root
            if not os.path.isabs(target):
                target = os.path.join(current_dir, target)
            target = os.path.abspath(target)
            real_target = os.path.realpath(target)
            if not real_target.startswith(os.path.realpath(session.workspace_root)):
                return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."
            current_dir = real_target
        elif "cd .." in sub_cmd or "cd/" in sub_cmd or re.search(r'\bcd\b.*\.\.', sub_cmd):
            return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."

    from ..shell_adapter import ShellAdapter
    shell_executable = ShellAdapter.get_shell_executable(interactive=False)

    # A2: resolve dynamic timeout
    timeout = _resolve_timeout(command, timeout_seconds)

    # A3: build environment with CI flags so scaffolding tools skip prompts
    env = os.environ.copy()
    env["CI"] = "true"
    env["npm_config_yes"] = "true"

    kwargs: Dict[str, Any] = {
        "stdin": asyncio.subprocess.DEVNULL,  # A3: never read from parent stdin
        "env": env,
    }
    if sys.platform == "win32":
        import subprocess
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    start_time = time.time()

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
            if elapsed > timeout:
                try:
                    if sys.platform == "win32":
                        subprocess.call(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        import signal
                        os.killpg(process.pid, signal.SIGTERM)
                except Exception:
                    pass
                partial = "".join(output_chunks)
                timeout_msg = f"Failed to execute command: Command timed out after {timeout:.0f} seconds."
                if partial:
                    return f"{timeout_msg}\n\nPartial output before timeout:\n{partial}"
                return timeout_msg

            try:
                line_bytes = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                output_chunks.append(line)
            except asyncio.TimeoutError:
                continue

        await process.wait()
        return "".join(output_chunks)

    except Exception as e:
        return f"Failed to execute command: {str(e)}"

