import os
import sys
import time
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


# NOTE: LocalSandbox (host-execution via subprocess.run(shell=True)) has been
# intentionally removed. It provided no real security boundary and silently ran
# agent commands directly on the host OS. There is exactly one secure execution
# path: DockerSandbox. If Docker is unavailable the factory raises RuntimeError
# so the failure is loud and explicit rather than silently insecure.


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
            raise RuntimeError(
                "Docker library is not installed. "
                "Install it with: pip install docker"
            )

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
    Factory function that creates a Docker-based isolated sandbox.

    LocalSandbox (host execution) has been removed permanently. The only
    supported execution environment is DockerSandbox. If Docker is unavailable
    this function raises RuntimeError with instructions rather than silently
    falling back to host-OS execution.

    Raises:
        RuntimeError: When Docker is not available or explicitly disabled.
    """
    if use_docker is False:
        raise RuntimeError(
            "Sandbox creation with use_docker=False is not allowed. "
            "Host execution (LocalSandbox) has been removed for security. "
            "Ensure Docker is installed and the daemon is running."
        )

    docker_mod, has_docker = _import_docker()
    if not has_docker:
        raise RuntimeError(
            "Docker library not found. Cannot create a secure execution sandbox. "
            "Install Docker SDK: pip install docker"
        )

    try:
        client = docker_mod.from_env()
        client.ping()
        logger.info("Docker daemon connectivity verified. Using DockerSandbox.")
        return DockerSandbox(image=image, registry=registry)
    except Exception as e:
        raise RuntimeError(
            f"Docker daemon not running or not accessible: {e}. "
            "Ensure the Docker daemon is running. "
            "Host-level execution fallback has been removed for security."
        ) from e
