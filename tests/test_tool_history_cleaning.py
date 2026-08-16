"""
Unit tests for Tool History Cleaning and Duplicate Tool Call ID Prevention.
"""

import pytest
from backend.app.adapters.tool_history import (
    ToolHistoryError,
    clean_tool_history,
    validate_tool_history,
)


def test_clean_tool_history_deduplicates_duplicate_tool_call_ids():
    """Verify that duplicate tool call IDs across assistant messages are deduplicated."""
    duplicate_history = [
        {"role": "user", "content": "RUN THE PROJECT"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "chatcmpl-tool-b04135da17b83c3f",
                    "name": "open_with_live_server",
                    "input": {"file_path": "index.html"},
                }
            ],
        },
        # Duplicate assistant message appended by runtime/session loop
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "chatcmpl-tool-b04135da17b83c3f",
                    "name": "open_with_live_server",
                    "input": {"file_path": "index.html"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "chatcmpl-tool-b04135da17b83c3f",
            "name": "open_with_live_server",
            "content": "Started server process on port 6005",
        },
        {"role": "user", "content": "RUN THE PROJECT AGAIN"},
    ]

    # Without cleaning, validate_tool_history MUST fail with duplicate ID error
    with pytest.raises(ToolHistoryError) as exc_info:
        validate_tool_history(duplicate_history)
    assert "Duplicate tool call id: chatcmpl-tool-b04135da17b83c3f" in str(exc_info.value)

    # With clean_tool_history, duplicate assistant tool calls are removed and validate_tool_history succeeds
    cleaned = clean_tool_history(duplicate_history)
    validate_tool_history(cleaned)

    # Check structure of cleaned history
    assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["tool_calls"][0]["id"] == "chatcmpl-tool-b04135da17b83c3f"


def test_clean_tool_history_handles_duplicate_tool_results():
    """Verify that duplicate tool results for the same tool_call_id are cleaned."""
    history = [
        {"role": "user", "content": "test"},
        {
            "role": "assistant",
            "content": "thinking",
            "tool_calls": [{"id": "call_123", "name": "read_file", "input": {"path": "a.txt"}}],
        },
        {"role": "tool", "tool_call_id": "call_123", "name": "read_file", "content": "content 1"},
        {"role": "tool", "tool_call_id": "call_123", "name": "read_file", "content": "content 2"},
    ]

    cleaned = clean_tool_history(history)
    validate_tool_history(cleaned)

    tool_msgs = [m for m in cleaned if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["content"] == "content 1"


def test_clean_tool_history_removes_orphaned_results():
    """Verify that tool results with no matching assistant tool call are removed."""
    history = [
        {"role": "user", "content": "test"},
        {"role": "tool", "tool_call_id": "orphan_999", "name": "read_file", "content": "data"},
    ]

    cleaned = clean_tool_history(history)
    validate_tool_history(cleaned)

    tool_msgs = [m for m in cleaned if m.get("role") == "tool"]
    assert len(tool_msgs) == 0


def test_clean_tool_history_removes_unresolved_tool_calls():
    """Verify that unresolved assistant tool calls (e.g. from interrupted turns) are stripped before next user message."""
    history = [
        {"role": "user", "content": "run project"},
        {
            "role": "assistant",
            "content": "Starting server...",
            "tool_calls": [{"id": "chatcmpl-tool-b04135da17b83c3f", "name": "open_with_live_server", "input": {}}],
        },
        # User message arrived without tool result (e.g. user cancelled or restarted)
        {"role": "user", "content": "hi"},
    ]

    cleaned = clean_tool_history(history)
    validate_tool_history(cleaned)

    assistant_msgs = [m for m in cleaned if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1
    # Tool calls stripped because it was never resolved
    assert "tool_calls" not in assistant_msgs[0]
    assert assistant_msgs[0]["content"] == "Starting server..."

