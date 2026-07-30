import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.tools.dispatcher import dispatch_tool

@pytest.fixture(autouse=True)
async def _stop_spawned_processes():
    yield
    from app.processes import global_process_manager
    for proc in list(global_process_manager.get_running_processes()):
        try:
            await proc.stop()
        except Exception:
            pass

class MockSession:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self._monitor_tasks = []  # B6: required by file_tools monitor task tracking

    async def send_ws_message(self, msg):
        pass

    async def monitor_and_stream_events(self, proc):
        pass

@pytest.mark.asyncio
async def test_tool_name_aliases(tmp_path):
    session = MockSession(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello world", encoding="utf-8")

    # Test list_files alias -> list_directory
    res_list = await dispatch_tool(session, "tc-1", "list_files", {}, auto_apply=True)
    assert "test.txt" in res_list

    # Test view_file alias -> read_file
    res_read = await dispatch_tool(session, "tc-2", "view_file", {"file": "test.txt"}, auto_apply=True)
    assert res_read == "hello world"

    # Test see_files alias -> list_directory
    res_see = await dispatch_tool(session, "tc-3", "see_files", {"dir": "."}, auto_apply=True)
    assert "test.txt" in res_see

@pytest.mark.asyncio
async def test_open_with_live_server_tool(tmp_path):
    session = MockSession(str(tmp_path))
    (tmp_path / "index.html").write_text("<h1>Test Live Server</h1>", encoding="utf-8")

    res = await dispatch_tool(session, "tc-4", "live_server", {"path": "index.html"}, auto_apply=True)
    assert "Live Server Started" in res
    import re
    assert re.search(r"http://localhost:\d+/index.html", res) is not None
