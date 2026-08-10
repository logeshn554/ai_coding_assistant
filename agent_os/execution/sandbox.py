import os
import sys
import time
import shutil
import tempfile
import subprocess
import logging
from typing import Any, Dict, Optional
from agent_os.execution.interfaces import ISandbox

logger = logging.getLogger("agentos.execution.sandbox")

def _import_docker():
    try:
        import docker
        return docker, True
    except ImportError:
        return None, False


class LocalSandbox(ISandbox):
    """Fallback local execution environment running commands in a temporary directory."""
    def __init__(self, workspace_root: Optional[str] = None, registry: Optional[Any] = None) -> None:
        self.workspace_root = workspace_root
        self.registry = registry
        self.sandbox_dir: Optional[str] = None

    def start(self) -> None:
        if self.workspace_root:
            os.makedirs(self.workspace_root, exist_ok=True)
            self.sandbox_dir = tempfile.mkdtemp(dir=self.workspace_root, prefix="sandbox_")
        else:
            self.sandbox_dir = tempfile.mkdtemp(prefix="sandbox_")
        logger.info(f"LocalSandbox started at {self.sandbox_dir}")

    def stop(self) -> None:
        if self.sandbox_dir and os.path.exists(self.sandbox_dir):
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)
            logger.info(f"LocalSandbox at {self.sandbox_dir} stopped and cleaned up")
            self.sandbox_dir = None

    def _vet_and_log_command(self, cmd: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        policy_engine = None
        audit_store = None
        if self.registry:
            try:
                from agent_os.kernel.policy_engine import PolicyEngine
                policy_engine = self.registry.resolve(PolicyEngine)
            except Exception:
                pass
            try:
                from agent_os.infrastructure.audit_store import AuditStore
                audit_store = self.registry.resolve(AuditStore)
            except Exception:
                pass

        if policy_engine:
            if not policy_engine.is_command_safe(cmd):
                if audit_store:
                    audit_store.log_action("run_command", "agent", cmd, "denied", {"reason": "Policy violation"})
                return False, {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Permission Denied: Command blocked by policy engine.",
                    "time_taken_seconds": 0.0
                }

        if audit_store:
            audit_store.log_action("run_command", "agent", cmd, "approved")

        return True, None

    def run_command(self, cmd: str) -> Dict[str, Any]:
        if not self.sandbox_dir:
            raise RuntimeError("LocalSandbox has not been started. Call start() first.")

        # Intercept and validate command using policy engine
        is_safe, err_res = self._vet_and_log_command(cmd)
        if not is_safe:
            return err_res

        start_time = time.monotonic()
        try:
            # Use shell execution with a safety timeout of 30 seconds
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=self.sandbox_dir,
                capture_output=True,
                text=True,
                timeout=30.0
            )
            time_taken = time.monotonic() - start_time
            
            # Log execution result
            audit_store = None
            if self.registry:
                try:
                    from agent_os.infrastructure.audit_store import AuditStore
                    audit_store = self.registry.resolve(AuditStore)
                except Exception:
                    pass
            if audit_store:
                status_str = "success" if res.returncode == 0 else "error"
                audit_store.log_action("run_command", "agent", cmd, status_str, {"exit_code": res.returncode})

            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "time_taken_seconds": round(time_taken, 3)
            }
        except subprocess.TimeoutExpired as te:
            time_taken = time.monotonic() - start_time
            
            audit_store = None
            if self.registry:
                try:
                    from agent_os.infrastructure.audit_store import AuditStore
                    audit_store = self.registry.resolve(AuditStore)
                except Exception:
                    pass
            if audit_store:
                audit_store.log_action("run_command", "agent", cmd, "error", {"reason": "Timeout"})

            return {
                "exit_code": -1,
                "stdout": te.stdout or "",
                "stderr": f"Command timed out after 30 seconds.\n{te.stderr or ''}",
                "time_taken_seconds": round(time_taken, 3)
            }
        except Exception as e:
            time_taken = time.monotonic() - start_time
            
            audit_store = None
            if self.registry:
                try:
                    from agent_os.infrastructure.audit_store import AuditStore
                    audit_store = self.registry.resolve(AuditStore)
                except Exception:
                    pass
            if audit_store:
                audit_store.log_action("run_command", "agent", cmd, "error", {"reason": str(e)})

            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution error: {e}",
                "time_taken_seconds": round(time_taken, 3)
            }


class DockerSandbox(ISandbox):
    """Safe docker container environment for isolated code execution."""
    def __init__(self, image: str = "python:3.12-slim", container_name: Optional[str] = None, registry: Optional[Any] = None) -> None:
        self.image = image
        self.container_name = container_name or f"agentos_sandbox_{int(time.time())}"
        self.registry = registry
        self.client: Optional[Any] = None
        self.container: Optional[Any] = None

    def start(self) -> None:
        docker_mod, has_docker = _import_docker()
        if not has_docker:
            raise RuntimeError("docker library is not installed.")

        try:
            self.client = docker_mod.from_env()
            logger.info(f"DockerSandbox: Pulling image '{self.image}' if not present...")
            self.client.images.pull(self.image)
            
            logger.info(f"DockerSandbox: Starting container '{self.container_name}'...")
            self.container = self.client.containers.run(
                self.image,
                command="tail -f /dev/null",
                name=self.container_name,
                detach=True,
                remove=True
            )
            logger.info(f"DockerSandbox: Container '{self.container_name}' started successfully.")
        except Exception as e:
            logger.error(f"DockerSandbox: Failed to start: {e}")
            raise RuntimeError(f"Failed to start DockerSandbox: {e}")

    def stop(self) -> None:
        if self.container:
            try:
                logger.info(f"DockerSandbox: Stopping and removing container '{self.container_name}'...")
                self.container.stop(timeout=2)
                logger.info(f"DockerSandbox: Container '{self.container_name}' stopped.")
            except Exception as e:
                logger.warning(f"DockerSandbox: Error stopping container: {e}")
            finally:
                self.container = None
        self.client = None

    def _vet_and_log_command(self, cmd: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        policy_engine = None
        audit_store = None
        if self.registry:
            try:
                from agent_os.kernel.policy_engine import PolicyEngine
                policy_engine = self.registry.resolve(PolicyEngine)
            except Exception:
                pass
            try:
                from agent_os.infrastructure.audit_store import AuditStore
                audit_store = self.registry.resolve(AuditStore)
            except Exception:
                pass

        if policy_engine:
            if not policy_engine.is_command_safe(cmd):
                if audit_store:
                    audit_store.log_action("run_command", "agent", cmd, "denied", {"reason": "Policy violation"})
                return False, {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Permission Denied: Command blocked by policy engine.",
                    "time_taken_seconds": 0.0
                }

        if audit_store:
            audit_store.log_action("run_command", "agent", cmd, "approved")

        return True, None

    def run_command(self, cmd: str) -> Dict[str, Any]:
        if not self.container:
            raise RuntimeError("DockerSandbox has not been started or has been stopped.")

        is_safe, err_res = self._vet_and_log_command(cmd)
        if not is_safe:
            return err_res

        start_time = time.monotonic()
        try:
            exec_res = self.container.exec_run(cmd, demux=True)
            time_taken = time.monotonic() - start_time
            
            exit_code = exec_res.exit_code
            stdout_bytes, stderr_bytes = exec_res.output or (b"", b"")
            
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            
            audit_store = None
            if self.registry:
                try:
                    from agent_os.infrastructure.audit_store import AuditStore
                    audit_store = self.registry.resolve(AuditStore)
                except Exception:
                    pass
            if audit_store:
                status_str = "success" if exit_code == 0 else "error"
                audit_store.log_action("run_command", "agent", cmd, status_str, {"exit_code": exit_code})

            return {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "time_taken_seconds": round(time_taken, 3)
            }
        except Exception as e:
            time_taken = time.monotonic() - start_time
            
            audit_store = None
            if self.registry:
                try:
                    from agent_os.infrastructure.audit_store import AuditStore
                    audit_store = self.registry.resolve(AuditStore)
                except Exception:
                    pass
            if audit_store:
                audit_store.log_action("run_command", "agent", cmd, "error", {"reason": str(e)})

            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Docker execution error: {e}",
                "time_taken_seconds": round(time_taken, 3)
            }


def create_sandbox(
    use_docker: Optional[bool] = None,
    image: str = "python:3.12-slim",
    workspace_root: Optional[str] = None,
    registry: Optional[Any] = None
) -> ISandbox:
    """
    Factory function to initialize the sandbox container lifecycle.
    Automatically probes Docker connectivity and falls back to LocalSandbox on failure.
    """
    if use_docker is False:
        return LocalSandbox(workspace_root=workspace_root, registry=registry)

    docker_mod, has_docker = _import_docker()
    if not has_docker:
        logger.warning("Docker library not found. Falling back to LocalSandbox.")
        return LocalSandbox(workspace_root=workspace_root, registry=registry)

    try:
        client = docker_mod.from_env()
        client.ping()
        logger.info("Docker daemon connectivity verified. Using DockerSandbox.")
        return DockerSandbox(image=image, registry=registry)
    except Exception as e:
        logger.warning(f"Docker daemon not running or not accessible ({e}). Falling back to LocalSandbox.")
        return LocalSandbox(workspace_root=workspace_root, registry=registry)
