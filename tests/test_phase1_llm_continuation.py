"""
Phase 1 Regression Test Suite — Verifies LLM continuation reliability, NVIDIA capabilities,
tool history validation, stream-to-non-stream fallback, tool call idempotency, and timeout formatting.
"""

import pytest
from backend.app.adapters.provider_capabilities import get_provider_capabilities, ProviderCapabilities
from backend.app.adapters.tool_history import validate_tool_history, has_tool_results, ToolHistoryError
from backend.app.agent.llm_retry import ToolIdempotencyRegistry
from backend.app.errors import LLMTimeoutError


def test_nvidia_provider_capabilities_policy():
    caps = get_provider_capabilities(
        provider="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        model_name="thinkingmachines/inkling",
    )
    assert caps.supports_streaming is True
    assert caps.supports_tools is True
    assert caps.supports_streaming_tool_continuation is False


def test_tool_history_validation_valid():
    messages = [
        {"role": "user", "content": "List directory"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_001",
                    "type": "function",
                    "function": {"name": "list_directory", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_001", "content": '["app.py"]'},
    ]
    assert has_tool_results(messages) is True
    validate_tool_history(messages)  # Should not raise


def test_tool_history_validation_orphan_result():
    messages = [
        {"role": "user", "content": "List directory"},
        {"role": "tool", "tool_call_id": "call_orphan", "content": "data"},
    ]
    with pytest.raises(ToolHistoryError) as exc_info:
        validate_tool_history(messages)
    assert "Orphan tool result" in str(exc_info.value)


def test_tool_history_validation_duplicate_call_id():
    messages = [
        {"role": "user", "content": "List directory"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_dup", "name": "read_file", "input": {}},
                {"id": "call_dup", "name": "write_file", "input": {}},
            ],
        },
    ]
    with pytest.raises(ToolHistoryError) as exc_info:
        validate_tool_history(messages)
    assert "Duplicate tool call id" in str(exc_info.value)


def test_tool_idempotency_registry():
    registry = ToolIdempotencyRegistry()
    assert registry.is_completed("call_101") is False

    registry.record_execution(
        tool_call_id="call_101",
        tool_name="list_directory",
        arguments={},
        status="success",
        result=["index.html"],
    )

    assert registry.is_completed("call_101") is True
    record = registry.get_completed_record("call_101")
    assert record is not None
    assert record.result == ["index.html"]


def test_llm_timeout_error_formatting():
    err = LLMTimeoutError(provider="openai", timeout_seconds=180.0)
    assert "timed out after 180s" in str(err)
