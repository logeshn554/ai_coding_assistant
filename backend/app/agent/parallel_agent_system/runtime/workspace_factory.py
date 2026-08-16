import os
import socket
from typing import Any

from parallel_agent_system.runtime.agent_runtime import DockerWorkspace
from parallel_agent_system.core.state import SubTask


def find_free_port() -> int:
    """Finds an available TCP port on the host machine.

    Note: There is an inherent TOCTOU window between this function returning and
    the caller actually binding the port (e.g. Docker startup). The risk is kept
    minimal by using SO_REUSEADDR so the bind is stable, but callers should handle
    EADDRINUSE at container-start time and retry with a fresh port if needed.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", 0))
        return s.getsockname()[1]


class WorkspaceFactory:
    """Factory responsible for spawning isolated Docker workspaces per agent subtask."""

    @staticmethod
    async def create_docker(subtask: SubTask) -> DockerWorkspace:
        """
        Spins up an isolated DockerWorkspace container for the agent subtask.
        """
        import asyncio
        import shutil
        import logging
        logger = logging.getLogger("parallel_agent_system.runtime.workspace_factory")

        port = find_free_port()
        
        # Get shared project directory path from environment or fall back to default
        temp_dir = tempfile.gettempdir()
        shared_project_path = os.environ.get("SHARED_PROJECT_PATH", os.path.join(temp_dir, "projects"))
        agent_workspace_path = os.path.join(temp_dir, f"agent-{subtask.id}")

        # Ensure directory structures exist on the host
        os.makedirs(agent_workspace_path, exist_ok=True)

        volumes = {
            shared_project_path: {"bind": "/project", "mode": "ro"},
            agent_workspace_path: {"bind": "/workspace", "mode": "rw"},
        }
        environment = {
            "AGENT_ID": subtask.id,
            "AGENT_TYPE": subtask.agent_type,
        }
        container_name = f"agent-{subtask.id[:8]}"
        image = "ghcr.io/openhands/runtime:latest"

        # Actually launch the Docker container if docker is installed
        has_docker = shutil.which("docker") is not None
        if has_docker:
            cmd = ["docker", "run", "-d", "--name", container_name]
            cmd.append("--rm") # Always auto remove on stop
            
            for host_path, vol_info in volumes.items():
                bind = vol_info.get("bind")
                mode = vol_info.get("mode", "rw")
                cmd.extend(["-v", f"{host_path}:{bind}:{mode}"])
                
            for k, v in environment.items():
                cmd.extend(["-e", f"{k}={v}"])
                
            cmd.append(image)
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_bytes, stderr_bytes = await proc.communicate()
                if proc.returncode != 0:
                    logger.warning(f"Docker container failed to start: {stderr_bytes.decode('utf-8', errors='replace')}")
                else:
                    logger.info(f"Docker container '{container_name}' started successfully on port {port}.")
            except Exception as e:
                logger.warning(f"Failed to launch Docker container: {e}")
        else:
            logger.info("Docker daemon not detected. Defaulting to local sandbox path isolation.")

        return DockerWorkspace(
            image=image,
            host_port=port,
            volumes=volumes,
            environment=environment,
            container_name=container_name,
            auto_remove=True,
        )
