"""Tests for Tavily web search fallback on recurring errors."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.web_search_tool import SearchResult, search_web


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
