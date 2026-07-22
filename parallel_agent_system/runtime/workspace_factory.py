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
        port = find_free_port()
        
        # Get shared project directory path from environment or fall back to default
        shared_project_path = os.environ.get("SHARED_PROJECT_PATH", "/tmp/projects")
        agent_workspace_path = f"/tmp/agent-{subtask.id}"

        # Ensure directory structures exist on the host
        os.makedirs(agent_workspace_path, exist_ok=True)

        return DockerWorkspace(
            image="ghcr.io/openhands/runtime:latest",
            host_port=port,
            volumes={
                shared_project_path: {"bind": "/project", "mode": "ro"},
                agent_workspace_path: {"bind": "/workspace", "mode": "rw"},
            },
            environment={
                "AGENT_ID": subtask.id,
                "AGENT_TYPE": subtask.agent_type,
            },
            container_name=f"agent-{subtask.id[:8]}",
            auto_remove=True,
        )
