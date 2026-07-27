"""Tests for Tavily web search fallback on recurring errors."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.web_search_tool import SearchResult, search_web
from parallel_agent_system.core.state import AgentResult, SubTask
from parallel_agent_system.monitor.stuck_detector import (
    StuckDetector,
    normalize_error_signature,
)


def test_error_signature_normalization():
    """Two errors differing only by line number/timestamp produce identical signatures."""
    err1 = (
        "2026-07-27T18:04:13 File '/app/src/main.py', line 42, in run\n"
        "TypeError: Cannot read property 'map' of undefined at 0x7fa8b9c10"
    )
    err2 = (
        "2026-07-27T19:15:00 File 'C:\\Users\\admin\\project\\main.py', line 99, in run\n"
        "TypeError: Cannot read property 'map' of undefined at 0x10b98a0"
    )

    sig1 = normalize_error_signature(err1)
    sig2 = normalize_error_signature(err2)

    assert sig1 == sig2
    assert "TypeError: Cannot read property 'map' of undefined" in sig1
    assert "line 42" not in sig1
    assert "0x7fa8b9c10" not in sig1

    diff_err = "ValueError: Invalid input parameter provided"
    assert normalize_error_signature(diff_err) != sig1


def test_stuck_detector_requires_debugging_agent_first():
    """StuckDetector flags web search only after threshold repeats AND debugging agent attempt."""
    detector = StuckDetector()
    subtask = SubTask(id="task-1", agent_type="code", description="Fix map error", workspace_dir="/tmp/workspace")
    err_output = "TypeError: Cannot read property 'map' of undefined"
    res1 = AgentResult(subtask_id="task-1", agent_type="code", status="failed", output=err_output, event_log_key="events:task-1")
    res2 = AgentResult(subtask_id="task-1", agent_type="code", status="failed", output=err_output, event_log_key="events:task-1")

    # 1. 2 errors but NO debugging agent attempt -> no web search
    det1 = detector.check_detailed([subtask], [res1, res2], repeat_error_threshold=2)
    assert "task-1" not in det1["web_search_task_ids"]

    # 2. Record Debugging Agent attempt
    detector.record_debugging_attempt("task-1")

    # 3. 2 errors + Debugging Agent attempted -> web search triggered!
    det2 = detector.check_detailed([subtask], [res1, res2], repeat_error_threshold=2)
    assert "task-1" in det2["web_search_task_ids"]


@pytest.mark.asyncio
async def test_search_web_returns_results_when_key_present():
    """search_web returns SearchResult list when TAVILY_API_KEY is configured."""
    mock_tavily_resp = {
        "results": [
            {
                "title": "Fixing Cannot read property map of undefined",
                "url": "https://stackoverflow.com/questions/123",
                "content": "Ensure target object is an array before calling .map()",
            }
        ]
    }

    with patch("app.state.config_manager.get_tavily_api_key", return_value="tvly-test-key-123"):
        with patch("tavily.TavilyClient.search", return_value=mock_tavily_resp):
            results = await search_web("TypeError: Cannot read property map of undefined")

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].title == "Fixing Cannot read property map of undefined"
    assert "stackoverflow.com" in results[0].url


@pytest.mark.asyncio
async def test_search_web_skips_cleanly_when_key_missing():
    """search_web returns empty list cleanly without crashing when TAVILY_API_KEY is missing."""
    with patch("app.state.config_manager.get_tavily_api_key", return_value=""):
        with patch.dict("os.environ", {"TAVILY_API_KEY": ""}, clear=True):
            results = await search_web("TypeError: Cannot read property map of undefined")

    assert results == []


@pytest.mark.asyncio
async def test_web_search_disabled_setting_prevents_trigger():
    """When web_search_fallback_enabled is False, feature never triggers."""
    with patch("app.state.config_manager.get_web_search_fallback_enabled", return_value=False):
        from app.tools.dispatcher import dispatch_tool

        class MockSession:
            workspace_root = "/tmp"

        res = await dispatch_tool(MockSession(), "tc-99", "search_web", {"query": "test error"}, auto_apply=True)
        assert "disabled in settings" in res
