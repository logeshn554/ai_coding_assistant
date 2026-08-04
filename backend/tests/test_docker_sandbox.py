"""Tests for Docker Sandbox Isolation and command wrapping logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.tools import terminal_tool
from app.config import settings


@pytest.fixture(autouse=True)
def reset_docker_cache():
    """Reset the docker available cache before and after each test."""
    terminal_tool._docker_available_cache = None
    yield
    terminal_tool._docker_available_cache = None


def test_is_docker_available_detects_missing_binary():
    """Verify that _is_docker_available returns False when docker is not installed."""
    with patch("shutil.which", return_value=None):
        assert not terminal_tool._is_docker_available()


def test_is_docker_available_handles_daemon_down():
    """Verify that _is_docker_available returns False if the docker command fails or timeout happens."""
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run", side_effect=Exception("daemon down")):
        assert not terminal_tool._is_docker_available()


def test_is_docker_available_caching():
    """Verify that _is_docker_available caches the result to avoid repeating subprocess calls."""
    with patch("shutil.which", return_value="/usr/bin/docker") as mock_which, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        # First call checks
        assert terminal_tool._is_docker_available()
        assert mock_which.call_count == 1
        assert mock_run.call_count == 1
        
        # Second call should use cache
        assert terminal_tool._is_docker_available()
        assert mock_which.call_count == 1
        assert mock_run.call_count == 1


def test_wrap_command_in_sandbox():
    """Verify docker command wrapping builds correct volumes and workdir arguments."""
    session = MagicMock()
    session.workspace_root = "/home/user/workspace"
    
    with patch("os.path.realpath", side_effect=lambda x: x.replace("\\", "/")), \
         patch("os.path.relpath", side_effect=lambda x, y: x.replace(y, "").strip("/")):
        # Sub-directory execution
        wrapped = terminal_tool._wrap_command_in_sandbox(
            session,
            command="pytest",
            current_dir="/home/user/workspace/tests/unit"
        )
        
        assert wrapped[0] == "docker"
        assert wrapped[1] == "run"
        assert "--rm" in wrapped
        assert "-i" in wrapped
        assert "-v" in wrapped
        assert "/home/user/workspace:/workspace" in wrapped
        assert "-w" in wrapped
        # The relative working directory inside the container should use forward-slashes
        assert wrapped[wrapped.index("-w") + 1] == "/workspace/tests/unit"
        assert wrapped[-1] == "pytest"


@pytest.mark.asyncio
async def test_run_shell_command_with_sandbox_enabled():
    """Verify run_shell_command calls docker run when sandbox is enabled and docker is available."""
    session = MagicMock()
    session.workspace_root = "/home/user/workspace"
    session.send_ws_message = AsyncMock()
    
    # Set settings
    old_use_sandbox = settings.USE_SANDBOX
    settings.USE_SANDBOX = True
    
    try:
        with patch("app.tools.terminal_tool._is_docker_available", return_value=True), \
             patch("asyncio.create_subprocess_exec") as mock_exec:
            
            # Setup mock process
            mock_proc = AsyncMock()
            mock_proc.pid = 12345
            mock_proc.stdout.readline.return_value = b""
            mock_proc.wait.return_value = 0
            mock_exec.return_value = mock_proc
            
            await terminal_tool.run_shell_command(session, "echo 'hello'")
            
            # Assert that create_subprocess_exec was called with docker command
            assert mock_exec.call_count == 1
            call_args = mock_exec.call_args[0]
            assert "docker" in call_args
            assert "run" in call_args
            assert "echo 'hello'" in call_args[-1]
            
    finally:
        settings.USE_SANDBOX = old_use_sandbox
