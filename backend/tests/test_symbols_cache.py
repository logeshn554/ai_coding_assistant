"""Tests for AST-Aware Workspace Symbols Cache and invalidation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.routes import workspace_symbols
from app.state import workspace_state
from app.tools.dispatcher import dispatch_tool, _maybe_update_knowledge_store
from app.cache import invalidate_pattern, cached


@pytest.fixture(autouse=True)
def mock_workspace_root(tmp_path):
    """Automatically mock workspace_state root with a temporary path."""
    old_root = workspace_state.root
    workspace_state.root = str(tmp_path)
    yield tmp_path
    workspace_state.root = old_root


@pytest.mark.asyncio
async def test_cached_decorator_stores_and_returns_symbols(tmp_path):
    """Verify that cached decorator works as expected on route handlers."""
    # Write a test file
    code_file = tmp_path / "foo.py"
    code_file.write_text("class Foo:\n    pass\n")

    # Mock _get_index to return our mock index
    mock_idx = MagicMock()
    mock_idx.get_symbols.return_value = [{"name": "Foo", "kindName": "class", "line": 1, "col": 1}]
    original_get_index = workspace_symbols._get_index
    workspace_symbols._get_index = lambda: mock_idx

    # First call - parses and caches
    res1 = await workspace_symbols.get_symbols(path="foo.py")
    assert res1["symbols"] == [{"name": "Foo", "kindName": "class", "line": 1, "col": 1}]
    assert mock_idx.get_symbols.call_count == 1

    try:
        # Second call - should return from cache without re-invoking the index function
        res2 = await workspace_symbols.get_symbols(path="foo.py")
        assert res2["symbols"] == [{"name": "Foo", "kindName": "class", "line": 1, "col": 1}]
        assert mock_idx.get_symbols.call_count == 1  # Still 1 call
    finally:
        workspace_symbols._get_index = original_get_index


@pytest.mark.asyncio
async def test_cache_invalidation_on_file_write(tmp_path):
    """Verify that writing/modifying a file invalidates cached symbols for that file."""
    # Mock invalidate_pattern function
    from app import cache
    original_invalidate = cache.invalidate_pattern
    mock_invalidate = AsyncMock(return_value=1)
    cache.invalidate_pattern = mock_invalidate

    try:
        session = MagicMock()
        session._knowledge_store = MagicMock()

        # Simulate update_knowledge_store (called after write_file/edit_file)
        _maybe_update_knowledge_store(session, "foo.py")

        # Allow background tasks to run briefly
        await asyncio.sleep(0.05)

        # Invalidate pattern should be called for foo.py and global symbols
        assert mock_invalidate.call_count >= 2
        calls = [c[0][0] for c in mock_invalidate.call_args_list]
        assert any("get_symbols" in c and "foo.py" in c for c in calls)
        assert any("get_global_symbols" in c for c in calls)

    finally:
        cache.invalidate_pattern = original_invalidate
