"""
Tests for workspace management (Phase 1d).
"""

import os
import tempfile
import pytest
from pathlib import Path

from agent_os.agent import Workspace, WorkspaceManager, WorkspaceHealth


class TestWorkspace:
    """Test workspace operations."""

    @pytest.mark.asyncio
    async def test_workspace_initialization(self):
        """Test workspace initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)

            success, message = await workspace.initialize()
            assert success
            assert workspace._is_initialized

    @pytest.mark.asyncio
    async def test_workspace_nonexistent_path(self):
        """Test workspace with nonexistent path creates it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = os.path.join(tmpdir, "new_workspace")
            workspace = Workspace(workspace_path)

            success, message = await workspace.initialize()
            assert success
            assert os.path.exists(workspace_path)

    @pytest.mark.asyncio
    async def test_workspace_health_check(self):
        """Test workspace health check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            health = await workspace.health_check()
            assert isinstance(health, WorkspaceHealth)
            assert health.is_healthy
            assert health.writable
            assert health.shell_works
            assert health.python_available

    @pytest.mark.asyncio
    async def test_workspace_run_command_success(self):
        """Test running a command in workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            result = await workspace.run_command("echo hello")
            assert result["success"]
            assert result["exit_code"] == 0
            assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_workspace_run_command_failure(self):
        """Test running a failing command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            result = await workspace.run_command("exit 1")
            assert not result["success"]
            assert result["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_workspace_run_command_timeout(self):
        """Test command timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            result = await workspace.run_command("sleep 10", timeout=1)
            assert not result["success"]
            assert result["exit_code"] == -1
            assert "timeout" in result["stderr"].lower()

    @pytest.mark.asyncio
    async def test_workspace_run_command_not_initialized(self):
        """Test that run_command fails if not initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)

            result = await workspace.run_command("echo test")
            assert not result["success"]
            assert result["exit_code"] == -1
            assert "not initialized" in result["stderr"]

    @pytest.mark.asyncio
    async def test_workspace_get_status(self):
        """Test getting workspace status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            status = workspace.get_status()
            assert status["initialized"]
            assert status["writable"]
            assert status["exists"]

    @pytest.mark.asyncio
    async def test_workspace_with_git_repo(self):
        """Test workspace detection of git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake git repo
            git_dir = os.path.join(tmpdir, ".git")
            os.makedirs(git_dir)

            workspace = Workspace(tmpdir)
            await workspace.initialize()

            health = await workspace.health_check()
            assert health.has_repository

    @pytest.mark.asyncio
    async def test_workspace_environment_variables(self):
        """Test passing environment variables to commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            env = {"TEST_VAR": "test_value"}
            if os.name == 'nt':  # Windows
                result = await workspace.run_command(
                    "echo %TEST_VAR%",
                    env=env
                )
            else:  # Unix
                result = await workspace.run_command(
                    "echo $TEST_VAR",
                    env=env
                )
            
            assert result["success"]

    @pytest.mark.asyncio
    async def test_workspace_file_creation_in_cwd(self):
        """Test that files created in commands exist in workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            await workspace.initialize()

            # Create a file via command
            result = await workspace.run_command('echo "test content" > test.txt')
            assert result["success"]

            # Verify file exists in workspace
            test_file = os.path.join(tmpdir, "test.txt")
            assert os.path.exists(test_file)


class TestWorkspaceManager:
    """Test workspace manager."""

    @pytest.mark.asyncio
    async def test_manager_create_workspace(self):
        """Test creating workspaces via manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager()

            workspace = manager.get_or_create_workspace("ws1", tmpdir)
            assert workspace is not None
            assert manager.get_workspace("ws1") is workspace

    @pytest.mark.asyncio
    async def test_manager_reuse_workspace(self):
        """Test that manager reuses existing workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager()

            ws1 = manager.get_or_create_workspace("ws1", tmpdir)
            ws2 = manager.get_or_create_workspace("ws1", tmpdir)

            assert ws1 is ws2

    @pytest.mark.asyncio
    async def test_manager_cleanup_workspace(self):
        """Test workspace cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager()

            workspace = manager.get_or_create_workspace("ws1", tmpdir)
            assert manager.get_workspace("ws1") is not None

            await manager.cleanup_workspace("ws1")
            assert manager.get_workspace("ws1") is None

    @pytest.mark.asyncio
    async def test_manager_cleanup_all(self):
        """Test cleaning up all workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                manager = WorkspaceManager()

                manager.get_or_create_workspace("ws1", tmpdir1)
                manager.get_or_create_workspace("ws2", tmpdir2)

                manager.cleanup_all()

                assert manager.get_workspace("ws1") is None
                assert manager.get_workspace("ws2") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
