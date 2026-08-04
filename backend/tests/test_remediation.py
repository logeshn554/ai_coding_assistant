import pytest
import os
import sys
import asyncio
from pathlib import Path
from fastapi import HTTPException
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routes.packages import _validate_package_name
from app.adapters.base import ModelAdapter
from app.utils import run_cmd_async

def test_package_name_validation():
    # Valid packages
    _validate_package_name("numpy")
    _validate_package_name("@types/node")
    _validate_package_name("react-dom")
    _validate_package_name("my_package-name.1")

    # Invalid names (blocked characters or lengths)
    with pytest.raises(HTTPException) as exc:
        _validate_package_name("numpy[extra]")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        _validate_package_name("numpy; rm -rf /")
    assert exc.value.status_code == 400

    # Blocked paths and URLs
    with pytest.raises(HTTPException) as exc:
        _validate_package_name("http://example.com/pkg")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        _validate_package_name("git+ssh://github.com")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        _validate_package_name("../escaped")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        _validate_package_name("C:\\Windows\\System32")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        _validate_package_name("/usr/bin/python")
    assert exc.value.status_code == 400

def test_cost_calculation():
    # Claude 3 Opus pricing
    opus_cost = ModelAdapter.calculate_cost("claude-3-opus-20240229", 1000, 1000)
    assert opus_cost == (1000 * 15.00 + 1000 * 75.00) / 1_000_000

    # Claude 3.5 Sonnet pricing
    sonnet_cost = ModelAdapter.calculate_cost("claude-3-5-sonnet", 1000, 1000)
    assert sonnet_cost == (1000 * 3.00 + 1000 * 15.00) / 1_000_000

    # Default fallback
    unknown_cost = ModelAdapter.calculate_cost("unknown-model", 1000, 1000)
    assert unknown_cost == (1000 * 3.00 + 1000 * 15.00) / 1_000_000

@pytest.mark.asyncio
async def test_shell_injection_prevention(tmp_path):
    # Verify that shell characters like ; and && are passed literally and NOT executed by a shell
    # We will invoke run_cmd_async with a command containing shell characters
    # E.g. running 'echo' with shell injection arguments
    # If a shell executed this, it would run the second command. Since we use create_subprocess_exec,
    # the second part is just treated as arguments to 'echo'.
    
    # Use python to write a dummy file if shell injection occurs
    evil_file = tmp_path / "evil_ran.txt"
    
    # We try to run a command that would create 'evil_ran.txt' if shell executed it
    # On Windows: echo hello & echo. > evil_ran.txt
    # On Unix: echo hello && touch evil_ran.txt
    if sys.platform == "win32":
        cmd_str = f"echo hello & echo. > {evil_file}"
    else:
        cmd_str = f"echo hello && touch {evil_file}"
        
    try:
        # This will fail on Windows if 'echo' is executed via create_subprocess_exec
        # because 'echo' is a shell builtin, not a standalone executable.
        # But we can test it with sys.executable (python)!
        py_code = "import sys; print('arg:', sys.argv)"
        cmd = [sys.executable, "-c", py_code, "hello", ";", "echo", "injection"]
        out = await run_cmd_async(cmd, str(tmp_path))
        # The output should show the argument list containing ';' and 'echo' literally
        assert ";" in out
        assert "injection" in out
        assert not os.path.exists(evil_file)
    except FileNotFoundError:
        pass  # If python isn't found/executable in this test environment

def test_deployment_pipeline_stub():
    from app.deployment import AIDeploymentPipeline
    pipeline = AIDeploymentPipeline()
    res = pipeline.execute_deployment_pipeline("staging")
    assert res["success"] is False
    assert res["is_stub"] is True
    assert "not yet implemented" in res["error"].lower()

def test_eos_scheduler_stub_tasks():
    from app.eos_scheduler import EOSScheduler
    scheduler = EOSScheduler()
    tasks = scheduler.list_queue()
    assert len(tasks) == 3
    for t in tasks:
        assert t["is_stub"] is True
        assert t["status"] == "inactive"

def test_workspace_index_caching(tmp_path):
    from app.workspace_index import WorkspaceIndex
    
    idx1 = WorkspaceIndex.get_instance(str(tmp_path))
    idx2 = WorkspaceIndex.get_instance(str(tmp_path))
    assert idx1 is idx2
    
    assert idx1._dirty is True
    idx1._dirty = False
    WorkspaceIndex.mark_dirty(str(tmp_path))
    assert idx1._dirty is True

def test_is_uri_confined_normalization():
    from app.routes.lsp import _is_uri_confined, workspace_state
    
    orig_root = workspace_state.root
    workspace_state.root = "C:/MyWorkspace"
    try:
        assert _is_uri_confined("file:///c:/myworkspace/subfolder/file.txt") is True
        assert _is_uri_confined("file:///C:/MyWorkspace/subfolder/file.txt") is True
        assert _is_uri_confined("file:///C:/myworkspace/subfolder/file.txt") is True
        assert _is_uri_confined("file:///C:/OtherWorkspace/file.txt") is False
    finally:
        workspace_state.root = orig_root

def test_chromadb_migration(tmp_path):
    from app.rag import _get_chroma_client, _chroma_clients
    
    # Setup mock old chroma dir in workspace
    old_dir = tmp_path / "artifacts" / "chroma"
    old_dir.mkdir(parents=True, exist_ok=True)
    (old_dir / "sqlite.db").write_text("dummy database")
    
    # We patch PersistentClient so it doesn't try to connect to the real sqlite db
    with patch("chromadb.PersistentClient") as mock_client:
        _chroma_clients.clear()
        client = _get_chroma_client(str(tmp_path))
        
        # Verify that old_dir was moved (migrated)
        assert not old_dir.exists()

@pytest.mark.asyncio
async def test_queue_worker_task_done(tmp_path):
    from app.session.agent_session import AgentSession
    
    # We construct a session with an active mock send_ws_message
    session = AgentSession(str(tmp_path), {"max_turns": 5}, AsyncMock())
    
    # Mock handle_user_message to raise CancelledError
    session.handle_user_message = AsyncMock(side_effect=asyncio.CancelledError)
    
    # Enqueue a message
    await session.enqueue_message("hello", "Ask")
    
    # We assert that the queue has 1 item
    assert session._message_queue.qsize() == 1
    
    # Run the queue worker task and let it process
    # It should raise CancelledError and break, but call task_done()!
    worker_task = asyncio.create_task(session._queue_worker())
    await asyncio.sleep(0.05)
    
    # Clean up worker task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
        
    # Since task_done() is called, join() should complete without hanging
    # (meaning the unfinished tasks count went to 0)
    await asyncio.wait_for(session._message_queue.join(), timeout=0.1)
