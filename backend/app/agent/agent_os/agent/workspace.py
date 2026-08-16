"""
Workspace management for agent execution.

Handles:
  - Workspace lifecycle (creation, validation, cleanup)
  - Repository detection and initialization
  - Shell command execution with proper stdio capture
  - Timeout and resource management
  - Real verification of workspace state
"""

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class WorkspaceError(Exception):
    """Workspace-related error."""


@dataclass
class WorkspaceHealth:
    """Health check result for workspace."""
    is_healthy: bool
    has_repository: bool
    shell_works: bool
    writable: bool
    free_space_mb: float
    python_available: bool
    issues: list[str]


class Workspace:
    """Manages execution workspace for agents."""

    def __init__(self, root_path: str):
        """
        Initialize workspace.

        Args:
            root_path: Path to workspace root
        """
        self.root_path = os.path.abspath(root_path)
        self._is_initialized = False
        self._health: WorkspaceHealth | None = None

    async def initialize(self) -> tuple[bool, str]:
        """
        Initialize workspace with validation.

        Returns:
            (success, message)
        """
        try:
            # 1. Create directory if needed
            os.makedirs(self.root_path, exist_ok=True)

            # 2. Verify writable
            if not os.access(self.root_path, os.W_OK):
                return False, f"Workspace not writable: {self.root_path}"

            # 3. Health check
            health = await self.health_check()
            if not health.is_healthy:
                issues = "; ".join(health.issues)
                return False, f"Workspace unhealthy: {issues}"

            self._is_initialized = True
            self._health = health

            logger.info(f"Workspace initialized: {self.root_path}")
            return True, "Workspace initialized"

        except Exception as e:
            return False, f"Failed to initialize workspace: {e!s}"

    async def health_check(self) -> WorkspaceHealth:
        """
        Perform comprehensive health check.

        Returns:
            WorkspaceHealth with detailed status
        """
        issues = []

        # 1. Check directory exists and is readable
        if not os.path.exists(self.root_path):
            issues.append(f"Workspace directory does not exist: {self.root_path}")
            return WorkspaceHealth(
                is_healthy=False,
                has_repository=False,
                shell_works=False,
                writable=False,
                free_space_mb=0,
                python_available=False,
                issues=issues,
            )

        # 2. Check writable
        writable = os.access(self.root_path, os.W_OK | os.X_OK)
        if not writable:
            issues.append(f"Workspace not writable: {self.root_path}")

        # 3. Check for repository (.git or other VCS)
        has_repository = os.path.exists(os.path.join(self.root_path, ".git"))

        # 4. Check shell works
        shell_works = await self._test_shell()
        if not shell_works:
            issues.append("Shell command execution failed")

        # 5. Check free space
        try:
            stat = shutil.disk_usage(self.root_path)
            free_space_mb = stat.free / (1024 * 1024)
            if free_space_mb < 100:
                issues.append(f"Low disk space: {free_space_mb:.1f} MB")
        except Exception as e:
            issues.append(f"Cannot check disk space: {e!s}")
            free_space_mb = 0

        # 6. Check Python available
        python_available = await self._test_python()
        if not python_available:
            issues.append("Python runtime not available")

        is_healthy = (
            writable
            and shell_works
            and python_available
            and free_space_mb > 100
        )

        return WorkspaceHealth(
            is_healthy=is_healthy,
            has_repository=has_repository,
            shell_works=shell_works,
            writable=writable,
            free_space_mb=free_space_mb,
            python_available=python_available,
            issues=issues,
        )

    async def _test_shell(self) -> bool:
        """Test shell command execution."""
        try:
            result = await self.run_command("echo test", timeout=5, _skip_init_check=True)
            return result["exit_code"] == 0
        except Exception:
            return False

    async def _test_python(self) -> bool:
        """Test Python availability."""
        try:
            import shutil
            import sys
            py_cmd = f'"{sys.executable}" --version' if not shutil.which("python") else "python --version"
            result = await self.run_command(py_cmd, timeout=5, _skip_init_check=True)
            return result["exit_code"] == 0
        except Exception:
            return False

    async def run_command(
        self,
        command: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
        _skip_init_check: bool = False,
    ) -> dict[str, Any]:
        """
        Execute a command in the workspace.

        Args:
            command: Shell command to run
            timeout: Timeout in seconds
            env: Environment variables to set
            _skip_init_check: Allow running command during health check initialization

        Returns:
            Dict with exit_code, stdout, stderr, duration_ms

        Never raises - always returns structured result.
        """
        if not self._is_initialized and not _skip_init_check:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Workspace not initialized",
                "duration_ms": 0,
                "success": False,
            }

        import time
        start_time = time.time()

        try:
            # Setup environment
            run_env = os.environ.copy()
            if env:
                run_env.update(env)

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root_path,
                env=run_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )

                duration_ms = (time.time() - start_time) * 1000

                return {
                    "exit_code": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "duration_ms": duration_ms,
                    "success": process.returncode == 0,
                }

            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                duration_ms = (time.time() - start_time) * 1000

                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Command timed out (timeout) after {timeout}s",
                    "duration_ms": duration_ms,
                    "success": False,
                }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms,
                "success": False,
            }

    def cleanup(self) -> None:
        """Clean up workspace resources."""
        if self._is_initialized:
            self._is_initialized = False
            logger.info(f"Workspace cleaned up: {self.root_path}")

    def get_status(self) -> dict[str, Any]:
        """Get workspace status."""
        return {
            "root_path": self.root_path,
            "initialized": self._is_initialized,
            "exists": os.path.exists(self.root_path),
            "writable": os.access(self.root_path, os.W_OK) if os.path.exists(self.root_path) else False,
            "has_git": os.path.exists(os.path.join(self.root_path, ".git")),
            "health": self._health.__dict__ if self._health else None,
        }


class WorkspaceManager:
    """Manages multiple workspaces."""

    def __init__(self):
        self._workspaces: dict[str, Workspace] = {}

    def get_or_create_workspace(self, workspace_id: str, root_path: str) -> Workspace:
        """Get or create a workspace."""
        if workspace_id not in self._workspaces:
            self._workspaces[workspace_id] = Workspace(root_path)
        return self._workspaces[workspace_id]

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        """Get an existing workspace."""
        return self._workspaces.get(workspace_id)

    async def cleanup_workspace(self, workspace_id: str) -> None:
        """Clean up a workspace."""
        if workspace_id in self._workspaces:
            self._workspaces[workspace_id].cleanup()
            del self._workspaces[workspace_id]

    def cleanup_all(self) -> None:
        """Clean up all workspaces."""
        for workspace in self._workspaces.values():
            workspace.cleanup()
        self._workspaces.clear()
