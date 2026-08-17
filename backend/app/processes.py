import asyncio
import ctypes
import logging
import os
import re
import subprocess
import sys
import uuid
from typing import Any

logger = logging.getLogger("loopix.processes")

PROCESS_MAX_HISTORY = 100
PROCESS_MAX_LOG_BYTES = 5 * 1024 * 1024

_job_objects = []

def confine_subprocess(pid: int) -> int | None:
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                PROCESS_SET_QUOTA = 0x0100
                PROCESS_TERMINATE = 0x0001
                proc_handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
                if proc_handle:
                    success = kernel32.AssignProcessToJobObject(job, proc_handle)
                    kernel32.CloseHandle(proc_handle)
                    if success:
                        return job
                    else:
                        kernel32.CloseHandle(job)
        except Exception:
            pass
    return None

def kill_process_tree(pid: int) -> None:
    """Kill complete process tree for a given pid across Windows and Unix."""
    if not pid:
        return
    try:
        if sys.platform == "win32":
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            import signal
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception as e:
        logger.warning(f"Error killing process tree for PID {pid}: {e}")

class ActiveProcess:
    def __init__(self, command: str, cwd: str, name: str = None, session: Any = None):
        self.id = str(uuid.uuid4())
        self.command = command
        self.cwd = cwd
        self.name = name or command
        self.status = "starting"  # starting, running, stopped, failed, crashed
        self.port: int | None = None
        self.localhost_url: str | None = None
        self.network_url: str | None = None
        self.pid: int | None = None
        self.container_pid: int | None = None
        self.sandbox_id: str | None = None
        self.session = session
        self.logs: list[str] = []
        self.process: asyncio.subprocess.Process | None = None
        self.read_task: asyncio.Task | None = None
        self.port_conflict = False
        self.conflict_details = {}
        self.startup_success_event = asyncio.Event()
        self.win32_job_object: int | None = None

    async def start(self):
        logger.info(f"Starting process '{self.name}' with command: {self.command}")
        self.logs.append(f"Starting: {self.command}\n")

        # Determine sandbox mode
        from backend.app.config import settings
        from backend.app.tools.terminal_tool import _is_docker_available
        is_sandboxed_env = (settings.USE_SANDBOX or settings.ENVIRONMENT == "production")

        if is_sandboxed_env:
            if not _is_docker_available():
                self.status = "failed"
                err_msg = "Production Sandbox Unavailable: Docker daemon not reachable or CLI missing. Failing closed."
                self.logs.append(f"{err_msg}\n")
                logger.error(err_msg)
                self.startup_success_event.set()
                return

            # Docker isolated execution
            from backend.app.agent.security import (
                ExecutionPolicy,
                NetworkMode,
                global_sandbox_manager,
            )
            
            # Extract policy values from session or defaults
            net_mode = "NO_NETWORK"
            run_id = "default_run"
            workspace_id = "default_ws"
            workspace_root = self.cwd
            if self.session:
                if isinstance(self.session, str):
                    workspace_root = self.session
                else:
                    workspace_root = getattr(self.session, "workspace_root", self.cwd)
                    net_mode = getattr(self.session, "network_mode", "NO_NETWORK")
                    if isinstance(net_mode, NetworkMode):
                        net_mode = net_mode.value
                    run_id = getattr(self.session, "run_id", "default_run")
                    workspace_id = getattr(self.session, "workspace_id", "default_ws")
            
            policy = ExecutionPolicy(
                workspace_root=workspace_root,
                network_mode=net_mode,
                max_runtime_seconds=3600.0,
                allow_network=(net_mode in ("ALLOWLIST", "FULL", "FULL_NETWORK"))
            )
            
            try:
                sandbox = await global_sandbox_manager.get_or_create(
                    workspace_id=workspace_id,
                    run_id=run_id,
                    policy=policy
                )
                
                log_file_name = f".loopix_logs_{self.id}.txt"
                log_file_path = os.path.join(workspace_root, log_file_name)
                # Create empty file on host
                with open(log_file_path, "w", encoding="utf-8") as f:
                    f.write("")
                    
                # Run the background command inside container
                res = await sandbox.execute(
                    command=f"nohup {self.command} > /workspace/{log_file_name} 2>&1 & echo $!",
                    timeout=15.0,
                    cwd=self.cwd
                )
                
                output_pid = res.combined_output.strip()
                if res.success and output_pid.isdigit():
                    self.container_pid = int(output_pid)
                    self.sandbox_id = sandbox.sandbox_id
                    self.status = "running"
                    self.startup_success_event.set()
                    self.read_task = asyncio.create_task(self._read_container_logs(log_file_path))
                    logger.info(f"Background dev server started inside Docker sandbox {self.sandbox_id} with container PID {self.container_pid}")
                else:
                    raise RuntimeError(f"Failed to retrieve background process ID from sandbox: {res.stderr or res.combined_output}")
            except Exception as e:
                self.status = "failed"
                self.logs.append(f"Failed to spawn process in Docker sandbox: {e!s}\n")
                logger.error(f"Sandbox background process spawn failed: {e!s}")
                self.startup_success_event.set()

        else:
            # Local host execution
            import shlex
            import shutil

            if isinstance(self.command, list):
                cmd_args = self.command
            else:
                cmd_args = shlex.split(self.command)

            if not cmd_args:
                raise ValueError("Empty command list")

            if sys.platform == "win32" and cmd_args:
                resolved = shutil.which(cmd_args[0])
                if resolved:
                    cmd_args[0] = resolved

            kwargs = {}
            if sys.platform == "win32":
                import subprocess
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["start_new_session"] = True

            # Use isolated environment
            from backend.app.agent.security.environment_isolation import (
                EnvironmentIsolation,
            )
            env = EnvironmentIsolation.get_isolated_env()
            env["CI"] = "true"
            env["npm_config_yes"] = "true"

            try:
                self.process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=self.cwd,
                    env=env,
                    **kwargs
                )
                self.pid = self.process.pid
                self.status = "running"
                if sys.platform == "win32":
                    job = confine_subprocess(self.pid)
                    if job:
                        self.win32_job_object = job
                    else:
                        raise OSError("Failed to assign process to Windows Job Object for confinement.")
                self.startup_success_event.set()
                self.read_task = asyncio.create_task(self._read_output())
            except Exception as e:
                self.status = "failed"
                self.logs.append(f"Failed to spawn process: {e!s}\n")
                logger.error(f"Process spawn failed: {e!s}")
                self.startup_success_event.set()

    async def _read_container_logs(self, log_file_path: str):
        try:
            # Wait for file to exist
            while not os.path.exists(log_file_path):
                await asyncio.sleep(0.1)

            # Open and read logs
            with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                while self.status == "running":
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        # Check container process liveness
                        inspect_proc = await asyncio.create_subprocess_exec(
                            "docker", "exec", self.sandbox_id, "kill", "-0", str(self.container_pid),
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL
                        )
                        exit_code = await inspect_proc.wait()
                        if exit_code != 0:
                            self.status = "stopped"
                            self.logs.append("\nProcess exited inside sandbox.\n")
                            break
                        continue

                    self.logs.append(line)
                    # Truncate
                    total_bytes = sum(len(l) for l in self.logs)
                    while total_bytes > 5 * 1024 * 1024 and len(self.logs) > 1:
                        removed = self.logs.pop(0)
                        total_bytes -= len(removed)

                    self._parse_line(line)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logs.append(f"\nError reading sandbox output logs: {e!s}\n")

    async def _read_output(self):
        try:
            while self.process and self.process.stdout:
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break
                if len(line_bytes) > 1024 * 1024:
                    line_bytes = line_bytes[:1024 * 1024] + b" ... [truncated line]\n"
                line = line_bytes.decode("utf-8", errors="replace")
                self.logs.append(line)
                
                # Truncate logs if too large by total byte length (>5MB)
                total_bytes = sum(len(l) for l in self.logs)
                while total_bytes > 5 * 1024 * 1024 and len(self.logs) > 1:
                    removed = self.logs.pop(0)
                    total_bytes -= len(removed)
                
                self._parse_line(line)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logs.append(f"\nError reading output: {e!s}\n")
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
        # Strip ANSI escape codes before URL/port parsing
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        clean_line = ansi_escape.sub('', line)

        # 1. Parse URLs
        urls = re.findall(r'https?://[^\s/$,;?#()]+(?::\d+)?', clean_line)
        for url in urls:
            url = url.rstrip("/")
            if "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url:  # nosec B104
                self.localhost_url = url
                port_match = re.search(r':(\d+)', url)
                if port_match:
                    self.port = int(port_match.group(1))
                if self.status == "starting":
                    self.status = "running"
                    self.startup_success_event.set()
            else:
                self.network_url = url
                if not self.port:
                    port_match = re.search(r':(\d+)', url)
                    if port_match:
                        self.port = int(port_match.group(1))
                if self.status == "starting":
                    self.status = "running"
                    self.startup_success_event.set()

        port_match = re.search(r'\b(?:port|Port|listening on|listening on port|Tomcat started on port\(s\):?)\s*:?\s*(\d{4,5})\b', clean_line)
        if port_match:
            detected_port = int(port_match.group(1))
            self.port = detected_port
            if not self.localhost_url:
                self.localhost_url = f"http://localhost:{detected_port}"
            if self.status == "starting":
                self.status = "running"
                self.startup_success_event.set()

        if any(pat in clean_line.lower() for pat in ["eaddrinuse", "address already in use", "port already in use", "could not bind"]):
            self.port_conflict = True
            self.status = "failed"
            conf_port_match = re.search(r'\b(?:port|Port|listening on|EADDRINUSE:?)\s*:?\s*(\d{4,5})\b', clean_line)
            if conf_port_match:
                self.port = int(conf_port_match.group(1))
            self.startup_success_event.set()

    async def check_tcp_readiness(self, host: str = "127.0.0.1", port: int | None = None) -> bool:
        target_port = port or self.port
        if not target_port:
            return False
        import socket
        try:
            sock = socket.create_connection((host, target_port), timeout=1.0)
            sock.close()
            return True
        except Exception:
            return False

    def cleanup(self):
        if sys.platform == "win32" and self.win32_job_object:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.win32_job_object)
            except Exception:
                pass
            self.win32_job_object = None

    async def stop(self):
        logger.info(f"Stopping process {self.id} ({self.name})")
        if self.process:
            try:
                if sys.platform == "win32":
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    import signal
                    os.killpg(self.process.pid, signal.SIGTERM)
            except Exception:
                pass

        if hasattr(self, "container_pid") and self.container_pid:
            try:
                stop_proc = await asyncio.create_subprocess_exec(
                    "docker", "exec", self.sandbox_id, "kill", "-9", str(self.container_pid),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await stop_proc.wait()
            except Exception as e:
                logger.warning(f"Error stopping container process {self.container_pid}: {e}")

        if self.win32_job_object:
            self.cleanup()

        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
            self.read_task = None

        if self.process:
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except Exception:
                try:
                    if sys.platform != "win32":
                        import signal
                        os.killpg(self.process.pid, signal.SIGKILL)
                    else:
                        self.process.kill()
                    await asyncio.wait_for(self.process.wait(), timeout=1.0)
                except Exception:
                    pass
            self.process = None
            self.status = "stopped"
            self.logs.append("\nProcess stopped by user.\n")

class ProcessManager:
    def __init__(self):
        self.processes: dict[str, ActiveProcess] = {}

    async def start_process(self, command: str, cwd: str, name: str = None, session: Any = None) -> ActiveProcess:
        # Enforce history limit of 100 non-running processes
        non_running = [p_id for p_id, p in self.processes.items() if p.status not in ("starting", "running")]
        if len(non_running) >= 100:
            for p_id in non_running[:10]:
                p = self.processes.pop(p_id, None)
                if p:
                    p.cleanup()

        # Create and start active process
        proc = ActiveProcess(command, cwd, name, session)
        self.processes[proc.id] = proc
        await proc.start()
        return proc

    async def stop_process(self, proc_id: str):
        if proc_id in self.processes:
            await self.processes[proc_id].stop()
            # We keep stopped processes in history to preserve logs,
            # but mark status as stopped

    def get_all_processes(self) -> list[ActiveProcess]:
        return list(self.processes.values())

    def get_running_processes(self) -> list[ActiveProcess]:
        return [p for p in self.processes.values() if p.status in ("starting", "running")]

    def get_process(self, proc_id: str) -> ActiveProcess | None:
        return self.processes.get(proc_id)

    def get_process_logs(self, proc_id: str) -> list[str]:
        proc = self.get_process(proc_id)
        return proc.logs if proc else []

# Global instance of process manager
global_process_manager = ProcessManager()

def get_process_using_port(port: int) -> tuple[int | None, str | None]:
    """
    Returns (pid, process_name) of the process listening on the specified port.
    """
    if sys.platform != "win32":
        # Unix/Linux/macOS using lsof
        try:
            output = subprocess.check_output(["lsof", "-t", f"-i:{port}"], stderr=subprocess.DEVNULL).decode("utf-8", errors="replace").strip()
            if output:
                pids = [int(p) for p in output.split() if p.isdigit()]
                if pids:
                    pid = pids[0]
                    name_output = subprocess.check_output(["ps", "-p", str(pid), "-o", "comm="], stderr=subprocess.DEVNULL).decode("utf-8", errors="replace").strip()
                    return pid, name_output
        except Exception:
            pass
        return None, None

    # Windows using netstat and tasklist
    try:
        output = subprocess.check_output(["netstat", "-ano"], stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")
        for line in output.splitlines():
            if "LISTENING" in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    local_addr = parts[1]
                    pid_str = parts[-1]
                    addr_parts = local_addr.rsplit(":", 1)
                    if len(addr_parts) == 2 and addr_parts[1] == str(port) and pid_str.isdigit():
                        pid = int(pid_str)
                        name_output = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/NH"], stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")
                        name_parts = name_output.strip().split()
                        process_name = name_parts[0] if name_parts else "Unknown"
                        return pid, process_name
    except Exception as e:
        logger.error(f"Error checking port conflict on {port}: {e!s}")
    return None, None

def kill_process_by_pid(pid: int) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.check_call(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 9)
        return True
    except Exception as e:
        logger.error(f"Failed to kill process {pid}: {e!s}")
        return False
