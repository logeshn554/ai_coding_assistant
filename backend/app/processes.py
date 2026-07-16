import asyncio
import os
import re
import sys
import logging
import subprocess
import uuid
import ctypes
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("devpilot.processes")

_job_objects = []

def confine_subprocess(pid: int):
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                PROCESS_SET_QUOTA = 0x0100
                PROCESS_TERMINATE = 0x0001
                proc_handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
                if proc_handle:
                    if kernel32.AssignProcessToJobObject(job, proc_handle):
                        _job_objects.append(job)
                    kernel32.CloseHandle(proc_handle)
        except Exception:
            pass

class ActiveProcess:
    def __init__(self, command: str, cwd: str, name: str = None):
        self.id = str(uuid.uuid4())
        self.command = command
        self.cwd = cwd
        self.name = name or command
        self.status = "starting"  # starting, running, stopped, failed, crashed
        self.port: Optional[int] = None
        self.localhost_url: Optional[str] = None
        self.network_url: Optional[str] = None
        self.pid: Optional[int] = None
        self.logs: List[str] = []
        self.process: Optional[asyncio.subprocess.Process] = None
        self.read_task: Optional[asyncio.Task] = None
        self.port_conflict = False
        self.conflict_details = {}
        self.startup_success_event = asyncio.Event()

    async def start(self):
        logger.info(f"Starting process '{self.name}' with command: {self.command}")
        self.logs.append(f"Starting: {self.command}\n")
        
        kwargs = {}
        if sys.platform == "win32":
            import subprocess
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
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

        try:
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.cwd,
                env=os.environ.copy(),
                **kwargs
            )
            self.pid = self.process.pid
            try:
                confine_subprocess(self.pid)
            except Exception:
                pass
            self.read_task = asyncio.create_task(self._read_output())
        except Exception as e:
            self.status = "failed"
            self.logs.append(f"Failed to spawn process: {str(e)}\n")
            logger.error(f"Process spawn failed: {str(e)}")

    async def _read_output(self):
        try:
            while self.process and self.process.stdout:
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                self.logs.append(line)
                
                # Truncate logs if too large
                if len(self.logs) > 1000:
                    self.logs = self.logs[-1000:]
                
                self._parse_line(line)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logs.append(f"\nError reading output: {str(e)}\n")
        finally:
            if self.process:
                exit_code = await self.process.wait()
                if self.status in ("starting", "running"):
                    if exit_code == 0:
                        self.status = "stopped"
                    else:
                        self.status = "crashed"
                self.logs.append(f"\nProcess exited with code {exit_code}\n")
                logger.info(f"Process {self.id} ({self.name}) exited with code {exit_code}")
                # Trigger event if exited so caller doesn't wait forever
                self.startup_success_event.set()

    def _parse_line(self, line: str):
        # 1. Parse URLs
        urls = re.findall(r'https?://[^\s/$,;?#()]+(?::\d+)?', line)
        for url in urls:
            # Strip trailing slashes or characters
            url = url.rstrip("/")
            if "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url:
                self.localhost_url = url
                # Extract port
                port_match = re.search(r':(\d+)', url)
                if port_match:
                    self.port = int(port_match.group(1))
                if self.status == "starting":
                    self.status = "running"
                    self.startup_success_event.set()
            else:
                self.network_url = url
                # Extract port if not already set
                if not self.port:
                    port_match = re.search(r':(\d+)', url)
                    if port_match:
                        self.port = int(port_match.group(1))
                if self.status == "starting":
                    self.status = "running"
                    self.startup_success_event.set()

        # 2. Check for port listening indicators (e.g. listening on port 3000, Listening on 8080, Tomcat started on port(s): 8080)
        port_match = re.search(r'\b(?:port|Port|listening on|listening on port|Tomcat started on port\(s\):?)\s*:?\s*(\d{4,5})\b', line)
        if port_match:
            detected_port = int(port_match.group(1))
            self.port = detected_port
            if not self.localhost_url:
                self.localhost_url = f"http://localhost:{detected_port}"
            if self.status == "starting":
                self.status = "running"
                self.startup_success_event.set()

        # 3. Check for port conflicts (EADDRINUSE, Address already in use, Port already in use)
        if any(pat in line.lower() for pat in ["eaddrinuse", "address already in use", "port already in use", "could not bind"]):
            self.port_conflict = True
            self.status = "failed"
            # Try to parse the port in conflict
            conf_port_match = re.search(r'\b(?:port|Port|listening on|EADDRINUSE:?)\s*:?\s*(\d{4,5})\b', line)
            if conf_port_match:
                self.port = int(conf_port_match.group(1))
            self.startup_success_event.set()

    async def stop(self):
        logger.info(f"Stopping process {self.id} ({self.name})")
        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
            self.read_task = None

        if self.process:
            try:
                if sys.platform == "win32":
                    # Taskkill tree of processes
                    subprocess.call(f"taskkill /F /T /PID {self.process.pid}", shell=True)
                else:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            self.status = "stopped"
            self.logs.append("\nProcess stopped by user.\n")

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, ActiveProcess] = {}

    async def start_process(self, command: str, cwd: str, name: str = None) -> ActiveProcess:
        # Create and start active process
        proc = ActiveProcess(command, cwd, name)
        self.processes[proc.id] = proc
        await proc.start()
        return proc

    async def stop_process(self, proc_id: str):
        if proc_id in self.processes:
            await self.processes[proc_id].stop()
            # We keep stopped processes in history to preserve logs,
            # but mark status as stopped

    def get_all_processes(self) -> List[ActiveProcess]:
        return list(self.processes.values())

    def get_running_processes(self) -> List[ActiveProcess]:
        return [p for p in self.processes.values() if p.status in ("starting", "running")]

    def get_process(self, proc_id: str) -> Optional[ActiveProcess]:
        return self.processes.get(proc_id)

    def get_process_logs(self, proc_id: str) -> List[str]:
        proc = self.get_process(proc_id)
        return proc.logs if proc else []

# Global instance of process manager
global_process_manager = ProcessManager()

def get_process_using_port(port: int) -> Tuple[Optional[int], Optional[str]]:
    """
    Returns (pid, process_name) of the process listening on the specified port.
    """
    if sys.platform != "win32":
        # Unix/Linux/macOS using lsof
        try:
            output = subprocess.check_output(f"lsof -t -i:{port}", shell=True).decode("utf-8", errors="replace").strip()
            if output:
                pids = [int(p) for p in output.split() if p.isdigit()]
                if pids:
                    pid = pids[0]
                    name_output = subprocess.check_output(f"ps -p {pid} -o comm=", shell=True).decode("utf-8", errors="replace").strip()
                    return pid, name_output
        except Exception:
            pass
        return None, None

    # Windows using netstat and tasklist
    try:
        output = subprocess.check_output("netstat -ano", shell=True).decode("utf-8", errors="replace")
        for line in output.splitlines():
            if "LISTENING" in line and f":{port}" in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = int(parts[-1])
                    name_output = subprocess.check_output(f"tasklist /FI \"PID eq {pid}\" /NH", shell=True).decode("utf-8", errors="replace")
                    name_parts = name_output.strip().split()
                    process_name = name_parts[0] if name_parts else "Unknown"
                    return pid, process_name
    except Exception as e:
        logger.error(f"Error checking port conflict on {port}: {str(e)}")
    return None, None

def kill_process_by_pid(pid: int) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.check_call(f"taskkill /F /PID {pid}", shell=True)
        else:
            subprocess.check_call(f"kill -9 {pid}", shell=True)
        return True
    except Exception as e:
        logger.error(f"Failed to kill process {pid}: {str(e)}")
        return False
