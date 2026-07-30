import os
import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.files import search_workspace_codebase, _search_with_ripgrep
from app.state import workspace_state

client = TestClient(app)

def test_ripgrep_search_and_fallback(tmp_path):
    # Setup test workspace with sample files
    f1 = tmp_path / "sample.txt"
    f1.write_text("hello devpilot ripgrep search line\nanother line here")

    f2 = tmp_path / "ignore.bin"
    f2.write_bytes(b"\x00\x01\x02binary")

    # Test ripgrep / python fallback search
    results = search_workspace_codebase(str(tmp_path), "devpilot")
    assert len(results) >= 1
    assert results[0]["path"] == "sample.txt"
    assert "devpilot" in results[0]["content"].lower()

    # Test empty query handling
    empty_res = search_workspace_codebase(str(tmp_path), "")
    assert empty_res == []

def test_git_blame_endpoint_no_workspace():
    # Workspace root unset or invalid
    orig = workspace_state.root
    workspace_state.root = None
    try:
        res = client.get("/api/git/blame?path=main.py")
        assert res.status_code == 400
    finally:
        workspace_state.root = orig

def test_git_blame_endpoint_nonexistent_file(tmp_path):
    orig = workspace_state.root
    workspace_state.root = str(tmp_path)
    try:
        res = client.get("/api/git/blame?path=nonexistent_file.txt")
        assert res.status_code == 404
    finally:
        workspace_state.root = orig

def test_dap_debug_endpoints(tmp_path):
    orig = workspace_state.root
    workspace_state.root = str(tmp_path)
    try:
        # 1. Status
        res = client.get("/api/debug/status")
        assert res.status_code == 200
        assert "running" in res.json()

        # 2. Breakpoints
        res = client.get("/api/debug/breakpoints")
        assert res.status_code == 200
        assert "breakpoints" in res.json()

        # 3. Add Breakpoint
        res = client.post("/api/debug/breakpoints", json={"file": "main.py", "line": 15, "enabled": True})
        assert res.status_code == 200
        assert res.json()["success"] is True

        # 4. Toggle Breakpoint
        bp_id = res.json()["breakpoint"]["id"]
        res = client.post("/api/debug/breakpoints/toggle", json={"breakpoint_id": bp_id})
        assert res.status_code == 200
        assert res.json()["success"] is True

        # 5. Evaluate Expression — DAP not connected, expect safe refusal (S2 fix)
        res = client.post("/api/debug/evaluate", json={"expression": "1 + 1"})
        assert res.status_code == 200
        assert res.json()["status"] == "no_session"  # eval() fallback removed for security

        # 6. Callstack
        res = client.get("/api/debug/callstack")
        assert res.status_code == 200
        assert "stack" in res.json()

        # 7. Step controls
        res = client.post("/api/debug/step-over")
        assert res.status_code == 200
    finally:
        workspace_state.root = orig
