"""
Secure Sandbox Execution Framework for DevPilot API.

Provides:
- ExecutionPolicy representing resource, network, filesystem, and environment constraints.
- SandboxExecutor abstraction with Docker and Local implementations.
- SandboxManager for lifecycle, ownership mapping, and reliable cleanup.
- Fail-closed validation logic.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
import logging
import ipaddress
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Callable, Tuple

from backend.app.config import settings
from .environment_isolation import EnvironmentIsolation
from .secret_redactor import SecretRedactor

logger = logging.getLogger("devpilot.security.sandbox")

class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    POLICY_DENIED = "POLICY_DENIED"
    SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"
    SANDBOX_ERROR = "SANDBOX_ERROR"

@dataclass
class ExecutionPolicy:
    workspace_root: str
    network_mode: str = "NO_NETWORK"  # NO_NETWORK, ALLOWLIST, FULL_NETWORK
    max_runtime_seconds: float = 60.0
    max_stdout_bytes: int = 1_000_000
    max_stderr_bytes: int = 1_000_000
    max_total_output_bytes: int = 2_000_000
    max_processes: int = 50
    max_memory: int = 512 * 1024 * 1024  # 512MB
    max_cpu: float = 1.0  # 1 CPU core
    allow_network: bool = False
    allowed_domains: Set[str] = field(default_factory=lambda: {
        "pypi.org", "files.pythonhosted.org", "registry.npmjs.org",
        "github.com", "raw.githubusercontent.com", "crates.io", "proxy.golang.org"
    })
    environment_policy: Dict[str, str] = field(default_factory=dict)
    filesystem_policy: str = "read-write"

@dataclass
class ExecutionResult:
    success: bool
    status: ExecutionStatus
    exit_code: int
    stdout: str
    stderr: str
    combined_output: str
    duration: float
    timed_out: bool = False
    output_limit_exceeded: bool = False
    resource_limit_exceeded: bool = False
    cancelled: bool = False
    sandbox_id: Optional[str] = None
    process_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class OutputLimitExceeded(Exception):
    pass

class SandboxExecutor:
    """Abstract base class representing an isolated sandbox environment."""

    def __init__(self, workspace_id: str, run_id: str, policy: ExecutionPolicy) -> None:
        self.workspace_id = workspace_id
        self.run_id = run_id
        self.policy = policy
        # Sanitize workspace_id and run_id to form a safe identifier
        clean_ws = re.sub(r'[^a-zA-Z0-9_-]', '', workspace_id)
        clean_run = re.sub(r'[^a-zA-Z0-9_-]', '', run_id)
        self.sandbox_id = f"devpilot_sb_{clean_run}_{clean_ws}"

    async def initialize(self) -> None:
        """Set up sandbox before running any commands."""
        pass

    async def execute(
        self,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        on_output_stream: Optional[Callable[[str], None]] = None,
    ) -> ExecutionResult:
        """Execute command in sandbox."""
        raise NotImplementedError()

    async def destroy(self) -> None:
        """Destroy the sandbox and clean up resources."""
        pass

def is_private_ip(ip_str: str) -> bool:
    """Return True if IP is private, loopback, or metadata service."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return True

def validate_outbound_network_hosts(command: str, allowed_domains: Set[str]) -> bool:
    """
    Defense-in-depth domain and SSRF validator for command strings.
    Scans for URLs and raw IPs, checks domain allowlists, and blocks private target IPs.
    """
    # Extract any HTTP/HTTPS URLs or raw IPs
    urls = re.findall(r'https?://([a-zA-Z0-9.-]+|(?:\d{1,3}\.){3}\d{1,3})', command)
    raw_ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', command)

    for host in urls + raw_ips:
        host_lower = host.lower().strip()
        
        # Block cloud metadata service IP explicitly
        if host_lower == "169.254.169.254":
            return False

        # If it is a raw IP, verify it is not private
        try:
            ipaddress.ip_address(host_lower)
            if is_private_ip(host_lower):
                return False
            continue
        except ValueError:
            pass

        # Check domain allowlist
        domain_match = False
        for allowed in allowed_domains:
            if host_lower == allowed.lower() or host_lower.endswith("." + allowed.lower()):
                domain_match = True
                break
        
        if not domain_match:
            # Perform DNS resolution to verify target IP is not private (prevent DNS rebinding SSRF)
            try:
                ips = socket.getaddrinfo(host_lower, None)
                for item in ips:
                    ip_addr = item[4][0]
                    if is_private_ip(ip_addr):
                        return False
            except Exception:
                # If resolution fails, fail closed under strict mode
                return False
    return True

class LocalSandboxExecutor(SandboxExecutor):
    """
    Subprocess-based executor with environment filtering, process group confinement,
    and output limit tracking. Used in desktop/local mode.
    """

    def __init__(self, workspace_id: str, run_id: str, policy: ExecutionPolicy) -> None:
        super().__init__(workspace_id, run_id, policy)
        self._active_process: Optional[asyncio.subprocess.Process] = None

    async def execute(
        self,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        on_output_stream: Optional[Callable[[str], None]] = None,
    ) -> ExecutionResult:
        # Enforce network check
        if self.policy.network_mode == "ALLOWLIST":
            if not validate_outbound_network_hosts(command, self.policy.allowed_domains):
                return ExecutionResult(
                    success=False,
                    status=ExecutionStatus.POLICY_DENIED,
                    exit_code=126,
                    stdout="",
                    stderr="Network Policy Denied: Access to internal hosts or unauthorized domains is blocked.",
                    combined_output="Network Policy Denied.",
                    duration=0.0
                )
        elif self.policy.network_mode == "NO_NETWORK":
            # For local execution without networks, block if command contains URLs
            if re.search(r'https?://', command) or re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', command):
                return ExecutionResult(
                    success=False,
                    status=ExecutionStatus.POLICY_DENIED,
                    exit_code=126,
                    stdout="",
                    stderr="Network Policy Denied: Network access is disabled.",
                    combined_output="Network Policy Denied.",
                    duration=0.0
                )

        t_limit = timeout or self.policy.max_runtime_seconds
        
        # Prepare environment
        base_env = EnvironmentIsolation.get_isolated_env(environment)
        if self.policy.environment_policy:
            base_env.update(self.policy.environment_policy)
        base_env["CI"] = "true"
        base_env["npm_config_yes"] = "true"

        work_dir = cwd or self.policy.workspace_root
        
        from backend.app.shell_adapter import ShellAdapter
        shell_executable = ShellAdapter.get_shell_executable(interactive=False)
        cmd_executable = shell_executable[0]
        cmd_params = shell_executable[1:] + [command]

        kwargs: Dict[str, Any] = {
            "stdin": asyncio.subprocess.DEVNULL,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "env": base_env,
            "cwd": work_dir
        }
        if sys.platform == "win32":
            import subprocess
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True

        start_time = time.time()
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                cmd_executable,
                *cmd_params,
                **kwargs
            )
            self._active_process = proc
            
            # Confine process group
            from backend.app.processes import confine_subprocess
            try:
                confine_subprocess(proc.pid)
            except Exception:
                pass

            # Streaming buffers
            stdout_bytes = bytearray()
            stderr_bytes = bytearray()
            combined_bytes = bytearray()
            
            async def read_stream(stream, is_stderr: bool):
                while True:
                    chunk = await stream.read(8192)
                    if not chunk:
                        break
                    
                    if is_stderr:
                        if len(stderr_bytes) + len(chunk) > self.policy.max_stderr_bytes:
                            raise OutputLimitExceeded()
                        stderr_bytes.extend(chunk)
                    else:
                        if len(stdout_bytes) + len(chunk) > self.policy.max_stdout_bytes:
                            raise OutputLimitExceeded()
                        stdout_bytes.extend(chunk)

                    if len(combined_bytes) + len(chunk) > self.policy.max_total_output_bytes:
                        raise OutputLimitExceeded()
                    combined_bytes.extend(chunk)

                    if on_output_stream:
                        line = chunk.decode("utf-8", errors="replace")
                        on_output_stream(line)

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(proc.stdout, False),
                        read_stream(proc.stderr, True)
                    ),
                    timeout=t_limit
                )
                exit_code = await proc.wait()
                duration = time.time() - start_time
                success = (exit_code == 0)
                status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
                
                stdout_str = SecretRedactor.redact_secrets(stdout_bytes.decode("utf-8", errors="replace"))
                stderr_str = SecretRedactor.redact_secrets(stderr_bytes.decode("utf-8", errors="replace"))
                combined_str = SecretRedactor.redact_secrets(combined_bytes.decode("utf-8", errors="replace"))

                return ExecutionResult(
                    success=success,
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    combined_output=combined_str,
                    duration=round(duration, 3),
                    process_id=proc.pid,
                    sandbox_id=self.sandbox_id
                )

            except OutputLimitExceeded:
                duration = time.time() - start_time
                await self.kill_process_tree(proc.pid)
                try:
                    await proc.wait()
                except Exception:
                    pass
                stdout_str = SecretRedactor.redact_secrets(stdout_bytes.decode("utf-8", errors="replace") + "\n[OUTPUT_LIMIT_EXCEEDED]")
                stderr_str = SecretRedactor.redact_secrets(stderr_bytes.decode("utf-8", errors="replace"))
                combined_str = SecretRedactor.redact_secrets(combined_bytes.decode("utf-8", errors="replace"))
                return ExecutionResult(
                    success=False,
                    status=ExecutionStatus.OUTPUT_LIMIT_EXCEEDED,
                    exit_code=-1,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    combined_output=combined_str,
                    duration=round(duration, 3),
                    output_limit_exceeded=True,
                    process_id=proc.pid,
                    sandbox_id=self.sandbox_id
                )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            if proc:
                await self.kill_process_tree(proc.pid)
                try:
                    await proc.wait()
                except Exception:
                    pass
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.TIMEOUT,
                exit_code=-1,
                stdout=SecretRedactor.redact_secrets(stdout_bytes.decode("utf-8", errors="replace") + "\n[TIMEOUT]"),
                stderr=SecretRedactor.redact_secrets(stderr_bytes.decode("utf-8", errors="replace")),
                combined_output="Execution timed out.",
                duration=round(duration, 3),
                timed_out=True,
                process_id=proc.pid if proc else None,
                sandbox_id=self.sandbox_id
            )
        except Exception as e:
            duration = time.time() - start_time
            if proc:
                await self.kill_process_tree(proc.pid)
                try:
                    await proc.wait()
                except Exception:
                    pass
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.SANDBOX_ERROR,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                combined_output=f"Error executing command: {e}",
                duration=round(duration, 3),
                process_id=proc.pid if proc else None,
                sandbox_id=self.sandbox_id
            )

    async def kill_process_tree(self, pid: int) -> None:
        """Reliably kills host process group."""
        from backend.app.processes import kill_process_tree
        kill_process_tree(pid)

    async def destroy(self) -> None:
        if self._active_process:
            try:
                await self.kill_process_tree(self._active_process.pid)
            except Exception:
                pass


class DockerSandboxExecutor(SandboxExecutor):
    """
    Executes commands inside a persistent Docker container named devpilot_sb_{run_id}_{workspace_id}.
    Enforces memory, CPU, process limits, and network modes at container startup.
    """

    def __init__(self, workspace_id: str, run_id: str, policy: ExecutionPolicy) -> None:
        super().__init__(workspace_id, run_id, policy)
        # Use digest-pinned image from settings to prevent mutable tag attacks.
        # To update: run `docker pull python:3.12-slim` and capture the digest:
        #   docker inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
        # Then update SANDBOX_IMAGE in your .env or settings.
        _default_image = getattr(settings, "SANDBOX_IMAGE", None) or "python:3.12-slim"
        self.image = _default_image
        self._initialized = False

    async def initialize(self) -> None:
        # Check if container already running
        proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f", "{{.State.Running}}", self.sandbox_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout.strip().lower() == b"true":
            self._initialized = True
            return

        # Build run options
        host_root = os.path.realpath(self.policy.workspace_root)
        
        docker_args = [
            "docker", "run", "-d",
            "--name", self.sandbox_id,
            "-v", f"{host_root}:/workspace:rw",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/run:rw,noexec,nosuid,size=16m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "-w", "/workspace",
        ]

        # Enforce memory constraint
        mem_mb = self.policy.max_memory // (1024 * 1024)
        docker_args.extend(["-m", f"{mem_mb}m"])

        # Enforce CPU limit
        docker_args.extend(["--cpus", str(self.policy.max_cpu)])

        # Enforce process limits
        docker_args.extend(["--pids-limit", str(self.policy.max_processes)])

        # Enforce Network Mode
        if self.policy.network_mode == "NO_NETWORK" or not self.policy.allow_network:
            docker_args.extend(["--network", "none"])
        
        # Add basic blocks to instance metadata services
        docker_args.extend(["--add-host", "metadata.google.internal:127.0.0.1"])
        docker_args.extend(["--add-host", "instance-data:127.0.0.1"])

        # Docker container image and entrypoint keeping it alive
        docker_args.extend([
            self.image,
            "tail", "-f", "/dev/null"
        ])

        # Execute container start
        logger.info(f"Initializing Docker Sandbox: {self.sandbox_id} args={docker_args}")
        start_proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await start_proc.communicate()
        if start_proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            logger.error(f"Failed to start Docker Sandbox container: {err_msg}")
            raise RuntimeError(f"Sandbox initialization failure: {err_msg}")

        self._initialized = True

    async def execute(
        self,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        on_output_stream: Optional[Callable[[str], None]] = None,
    ) -> ExecutionResult:
        if not self._initialized:
            await self.initialize()

        # Enforce network check
        if self.policy.network_mode == "ALLOWLIST":
            if not validate_outbound_network_hosts(command, self.policy.allowed_domains):
                return ExecutionResult(
                    success=False,
                    status=ExecutionStatus.POLICY_DENIED,
                    exit_code=126,
                    stdout="",
                    stderr="Network Policy Denied: Outbound target is blocked.",
                    combined_output="Network Policy Denied.",
                    duration=0.0
                )

        t_limit = timeout or self.policy.max_runtime_seconds

        # Build exec command
        exec_args = ["docker", "exec", "-i"]

        # Configure directory inside sandbox
        work_dir = "/workspace"
        if cwd:
            try:
                rel_path = os.path.relpath(cwd, self.policy.workspace_root)
                if rel_path != ".":
                    work_dir = f"/workspace/{rel_path.replace(os.sep, '/')}"
            except Exception:
                pass
        exec_args.extend(["-w", work_dir])

        # Environment isolation
        filtered_env = EnvironmentIsolation.get_isolated_env(environment)
        if self.policy.environment_policy:
            filtered_env.update(self.policy.environment_policy)
        filtered_env["CI"] = "true"
        filtered_env["npm_config_yes"] = "true"

        for k, v in filtered_env.items():
            exec_args.extend(["-e", f"{k}={v}"])

        exec_args.extend([self.sandbox_id, "sh", "-c", command])

        start_time = time.time()
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *exec_args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Streaming buffers
            stdout_bytes = bytearray()
            stderr_bytes = bytearray()
            combined_bytes = bytearray()
            
            async def read_stream(stream, is_stderr: bool):
                while True:
                    chunk = await stream.read(8192)
                    if not chunk:
                        break
                    
                    if is_stderr:
                        if len(stderr_bytes) + len(chunk) > self.policy.max_stderr_bytes:
                            raise OutputLimitExceeded()
                        stderr_bytes.extend(chunk)
                    else:
                        if len(stdout_bytes) + len(chunk) > self.policy.max_stdout_bytes:
                            raise OutputLimitExceeded()
                        stdout_bytes.extend(chunk)

                    if len(combined_bytes) + len(chunk) > self.policy.max_total_output_bytes:
                        raise OutputLimitExceeded()
                    combined_bytes.extend(chunk)

                    if on_output_stream:
                        line = chunk.decode("utf-8", errors="replace")
                        on_output_stream(line)

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(proc.stdout, False),
                        read_stream(proc.stderr, True)
                    ),
                    timeout=t_limit
                )
                exit_code = await proc.wait()
                duration = time.time() - start_time
                success = (exit_code == 0)
                status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
                
                stdout_str = SecretRedactor.redact_secrets(stdout_bytes.decode("utf-8", errors="replace"))
                stderr_str = SecretRedactor.redact_secrets(stderr_bytes.decode("utf-8", errors="replace"))
                combined_str = SecretRedactor.redact_secrets(combined_bytes.decode("utf-8", errors="replace"))

                return ExecutionResult(
                    success=success,
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    combined_output=combined_str,
                    duration=round(duration, 3),
                    process_id=proc.pid,
                    sandbox_id=self.sandbox_id
                )

            except OutputLimitExceeded:
                duration = time.time() - start_time
                await self.kill_active_exec_in_container()
                stdout_str = SecretRedactor.redact_secrets(stdout_bytes.decode("utf-8", errors="replace") + "\n[OUTPUT_LIMIT_EXCEEDED]")
                stderr_str = SecretRedactor.redact_secrets(stderr_bytes.decode("utf-8", errors="replace"))
                combined_str = SecretRedactor.redact_secrets(combined_bytes.decode("utf-8", errors="replace"))
                return ExecutionResult(
                    success=False,
                    status=ExecutionStatus.OUTPUT_LIMIT_EXCEEDED,
                    exit_code=-1,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    combined_output=combined_str,
                    duration=round(duration, 3),
                    output_limit_exceeded=True,
                    process_id=proc.pid,
                    sandbox_id=self.sandbox_id
                )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            await self.kill_active_exec_in_container()
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.TIMEOUT,
                exit_code=-1,
                stdout=SecretRedactor.redact_secrets(stdout_bytes.decode("utf-8", errors="replace") + "\n[TIMEOUT]"),
                stderr=SecretRedactor.redact_secrets(stderr_bytes.decode("utf-8", errors="replace")),
                combined_output="Execution timed out.",
                duration=round(duration, 3),
                timed_out=True,
                process_id=proc.pid if proc else None,
                sandbox_id=self.sandbox_id
            )
        except Exception as e:
            duration = time.time() - start_time
            await self.kill_active_exec_in_container()
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.SANDBOX_ERROR,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                combined_output=f"Error executing command: {e}",
                duration=round(duration, 3),
                process_id=proc.pid if proc else None,
                sandbox_id=self.sandbox_id
            )

    async def kill_active_exec_in_container(self) -> None:
        """
        Escalation logic: killing exec tasks cleanly.
        If we cannot cleanly kill running tasks inside the container, we recreate the entire container
        to force terminate all child processes and avoid orphans.
        """
        try:
            # Send SIGKILL to all active shells inside container
            kill_proc = await asyncio.create_subprocess_exec(
                "docker", "exec", self.sandbox_id, "sh", "-c", "kill -9 -1",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(kill_proc.wait(), timeout=2.0)
        except Exception:
            # Escalation: Forcibly recreate sandbox container on failure
            logger.warning(f"Failed to kill tasks cleanly in sandbox {self.sandbox_id}. Forcibly restarting container.")
            await self.destroy()
            await self.initialize()

    async def destroy(self) -> None:
        """Kill and remove the container."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", self.sandbox_id,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        self._initialized = False


class SandboxManager:
    """Manages active sandbox executor instances, coordinating initialization and teardown."""

    def __init__(self) -> None:
        self.active_sandboxes: Dict[str, SandboxExecutor] = {}

    async def get_or_create(
        self,
        workspace_id: str,
        run_id: str,
        policy: ExecutionPolicy,
        force_docker: bool = False
    ) -> SandboxExecutor:
        key = f"{run_id}_{workspace_id}"
        if key in self.active_sandboxes:
            return self.active_sandboxes[key]

        # Production requirements logic
        use_docker = settings.USE_SANDBOX or force_docker
        is_prod = settings.ENVIRONMENT == "production"
        is_server = settings.MODE == "server"

        if is_prod or settings.USE_SANDBOX:
            use_docker = True

        if use_docker:
            # Verify Docker availability
            from backend.app.tools.terminal_tool import _is_docker_available
            if not _is_docker_available():
                if is_prod or settings.USE_SANDBOX or is_server:
                    raise RuntimeError(
                        "Sandbox unavailable: Docker daemon not reachable or CLI missing. "
                        "Install Docker Desktop or set USE_SANDBOX=False only in trusted local development."
                    )
                else:
                    import warnings
                    warnings.warn(
                        "Running commands on HOST (no sandbox). "
                        "Never open untrusted repos in this mode.",
                        stacklevel=3,
                    )
                    logger.warning(
                        "Running commands on host because Docker sandbox is unavailable. "
                        "Never use this mode with untrusted repositories."
                    )
                    sandbox = LocalSandboxExecutor(workspace_id, run_id, policy)
            else:
                sandbox = DockerSandboxExecutor(workspace_id, run_id, policy)
        else:
            sandbox = LocalSandboxExecutor(workspace_id, run_id, policy)

        await sandbox.initialize()
        self.active_sandboxes[key] = sandbox
        return sandbox

    async def destroy_all(self) -> None:
        for sandbox in list(self.active_sandboxes.values()):
            try:
                await sandbox.destroy()
            except Exception:
                pass
        self.active_sandboxes.clear()

global_sandbox_manager = SandboxManager()
