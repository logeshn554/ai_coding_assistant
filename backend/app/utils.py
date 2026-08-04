import os
import sys
import asyncio
import re

from typing import Union, List

import shlex

async def run_cmd_async(cmd: Union[str, List[str]], cwd: str) -> str:
    kwargs = {}
    if sys.platform == "win32":
        import subprocess
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
        def drop_privileges():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
                resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))
            except Exception as e:
                raise RuntimeError(f"Fail-closed: could not drop privileges: {e}")
        kwargs["preexec_fn"] = drop_privileges

    if isinstance(cmd, str):
        if "cd .." in cmd or "cd/" in cmd or re.search(r'\bcd\b.*\.\.', cmd):
            raise PermissionError("Access denied: changing directory outside the workspace root is locked.")
        posix = (sys.platform != "win32")
        cmd_args = shlex.split(cmd, posix=posix)
    else:
        cmd_args = list(cmd)
        for item in cmd_args:
            if "cd .." in str(item) or "cd/" in str(item) or re.search(r'\bcd\b.*\.\.', str(item)):
                raise PermissionError("Access denied: changing directory outside the workspace root is locked.")

    proc = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
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
        try:
            if sys.platform == "win32":
                import subprocess
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)])
            else:
                proc.kill()
        except Exception:
            pass
        return "Command timed out after 30 seconds."
