import asyncio
import os
import re
import sys


async def run_cmd_async(cmd: str | list[str], cwd: str) -> str:
    # Build command string
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = str(cmd)

    # Clean directory traversals
    if "cd .." in cmd_str or "cd/" in cmd_str or re.search(r'\bcd\b.*\.\.', cmd_str):
        raise PermissionError("Access denied: changing directory outside the workspace root is locked.")

    # Determine if sandbox is mandatory or active
    from backend.app.config import settings
    from backend.app.tools.terminal_tool import _is_docker_available
    
    is_sandboxed_env = (settings.USE_SANDBOX or settings.ENVIRONMENT == "production")

    # Check if this is a safe host infrastructure command (e.g., git query commands)
    is_safe_infra = False
    cmd_lower = cmd_str.lower()
    if cmd_lower.startswith("git ") and not any(dangerous in cmd_lower for dangerous in ["clone", "push", "pull", "fetch"]):
        is_safe_infra = True

    if is_sandboxed_env and not is_safe_infra:
        if not _is_docker_available():
            raise RuntimeError(
                "Production Sandbox Unavailable: Docker daemon not reachable or CLI missing. "
                "Refusing host execution (fail-closed)."
            )

        # Retrieve or create sandbox
        from backend.app.agent.security.sandbox import (
            ExecutionPolicy,
            ExecutionStatus,
            global_sandbox_manager,
        )
        
        active_sandbox = None
        for sb in list(global_sandbox_manager.active_sandboxes.values()):
            if os.path.realpath(sb.policy.workspace_root) == os.path.realpath(cwd):
                active_sandbox = sb
                break
                
        if not active_sandbox:
            policy = ExecutionPolicy(
                workspace_root=cwd,
                network_mode="ALLOWLIST" if any(k in cmd_lower for k in ["npm", "pip", "yarn", "pnpm", "install"]) else "NO_NETWORK",
                allow_network=True
            )
            try:
                active_sandbox = await global_sandbox_manager.get_or_create(
                    workspace_id="api_route_ws",
                    run_id="api_route_run",
                    policy=policy
                )
            except Exception as e:
                raise RuntimeError(f"Sandbox creation failed: {e}. Refusing host execution (fail-closed).")

        if active_sandbox:
            res = await active_sandbox.execute(cmd_str, timeout=30.0, cwd=cwd)
            if res.status == ExecutionStatus.TIMEOUT:
                return "Command timed out after 30 seconds."
            return res.combined_output
        raise RuntimeError("Sandbox is unavailable. Refusing host execution (fail-closed).")

    # Local host fallback for development or safe infra
    # Use isolated environment
    from backend.app.agent.security.environment_isolation import EnvironmentIsolation
    env = EnvironmentIsolation.get_isolated_env()
    env["CI"] = "true"
    env["npm_config_yes"] = "true"

    kwargs = {}
    if sys.platform == "win32":
        import subprocess
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    if isinstance(cmd, list):
        cmd_args = list(cmd)
    else:
        import shlex
        posix = (sys.platform != "win32")
        cmd_args = shlex.split(cmd, posix=posix)

    proc = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
        **kwargs
    )
    
    from .processes import confine_subprocess
    try:
        confine_subprocess(proc.pid)
    except Exception:
        pass
        
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        return (stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")).strip()
    except asyncio.TimeoutError:
        from backend.app.processes import kill_process_tree
        kill_process_tree(proc.pid)
        return "Command timed out after 30 seconds."
