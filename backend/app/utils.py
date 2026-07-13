import os
import sys
import asyncio
import re

async def run_cmd_async(cmd: str, cwd: str) -> str:
    # Working directory lock check
    if "cd .." in cmd or "cd/" in cmd or re.search(r'\bcd\b.*\.\.', cmd):
        raise PermissionError("Access denied: changing directory outside the workspace root is locked.")

    kwargs = {}
    if sys.platform != "win32":
        kwargs["executable"] = "/bin/bash"
        import pwd
        def drop_privileges():
            try:
                nobody = pwd.getpwnam('nobody')
                os.setgid(nobody.pw_gid)
                os.setuid(nobody.pw_uid)
            except Exception:
                pass
        kwargs["preexec_fn"] = drop_privileges

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
