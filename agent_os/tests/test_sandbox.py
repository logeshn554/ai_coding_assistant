import os
import sys
from unittest.mock import MagicMock, patch

# Inject mock docker module to satisfy imports on systems without docker installed
mock_docker = MagicMock()
sys.modules["docker"] = mock_docker

import pytest
from agent_os.execution.sandbox import LocalSandbox, DockerSandbox, create_sandbox
import agent_os.execution.sandbox as sandbox_module

def test_local_sandbox_lifecycle():
    sandbox = LocalSandbox()
    
    # Not started yet
    with pytest.raises(RuntimeError):
        sandbox.run_command("echo hello")
        
    sandbox.start()
    assert sandbox.sandbox_dir is not None
    assert os.path.exists(sandbox.sandbox_dir)
    
    # Run basic echo
    res = sandbox.run_command("echo hello")
    assert res["exit_code"] == 0
    assert "hello" in res["stdout"].strip()
    assert res["time_taken_seconds"] >= 0.0
    
    sandbox.stop()
    assert sandbox.sandbox_dir is None

def test_docker_sandbox_lifecycle():
    # Reset mock docker
    mock_docker.reset_mock()
    
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_docker.from_env.return_value = mock_client
    mock_client.containers.run.return_value = mock_container
    
    # Mock exec_run output
    mock_exec_res = MagicMock()
    mock_exec_res.exit_code = 0
    mock_exec_res.output = (b"output_from_container", b"")
    mock_container.exec_run.return_value = mock_exec_res

    # Patch _import_docker to return our mock and True
    with patch("agent_os.execution.sandbox._import_docker", return_value=(mock_docker, True)):
        sandbox = DockerSandbox(image="my-dummy-image", container_name="test_sandbox_container")
        sandbox.start()
        
        # Verify container run call
        mock_client.containers.run.assert_called_once_with(
            "my-dummy-image",
            command="tail -f /dev/null",
            name="test_sandbox_container",
            detach=True,
            remove=True
        )
        
        # Exec command
        res = sandbox.run_command("python -c 'print(123)'")
        assert res["exit_code"] == 0
        assert res["stdout"] == "output_from_container"
        
        sandbox.stop()
        mock_container.stop.assert_called_once_with(timeout=2)

def test_create_sandbox_factory_fallback():
    # Reset mock docker
    mock_docker.reset_mock()
    
    # Forced local
    sandbox = create_sandbox(use_docker=False)
    assert isinstance(sandbox, LocalSandbox)
    
    # Successful probe
    mock_docker.from_env.return_value.ping.return_value = True
    with patch("agent_os.execution.sandbox._import_docker", return_value=(mock_docker, True)):
        sandbox = create_sandbox(use_docker=True)
        assert isinstance(sandbox, DockerSandbox)
        
        # Failed probe fallback to Local
        mock_docker.from_env.return_value.ping.side_effect = Exception("Daemon connection refused")
        sandbox = create_sandbox(use_docker=True)
        assert isinstance(sandbox, LocalSandbox)
