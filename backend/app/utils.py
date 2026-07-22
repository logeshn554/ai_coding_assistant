import os
import sys
import asyncio
import re

from typing import Union, List

async def run_cmd_async(cmd: Union[str, List[str]], cwd: str) -> str:
    kwargs = {}
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

    if isinstance(cmd, (list, tuple)):
        for item in cmd:
            if "cd .." in str(item) or "cd/" in str(item) or re.search(r'\bcd\b.*\.\.', str(item)):
                raise PermissionError("Access denied: changing directory outside the workspace root is locked.")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            **kwargs
        )
    else:
        # Working directory lock check
        if "cd .." in cmd or "cd/" in cmd or re.search(r'\bcd\b.*\.\.', cmd):
            raise PermissionError("Access denied: changing directory outside the workspace root is locked.")
        if sys.platform != "win32":
            kwargs["executable"] = "/bin/bash"
        proc = await asyncio.create_subprocess_shell(
            cmd,
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
                subprocess.call(f"taskkill /F /T /PID {proc.pid}", shell=True)
            else:
                proc.kill()
        except Exception:
            pass
        return "Command timed out after 30 seconds."
