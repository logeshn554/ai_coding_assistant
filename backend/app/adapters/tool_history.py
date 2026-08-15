"""
Tool History Validation Module — Enforces message structure integrity before sending to provider endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List
from ..errors import LLMProviderError


class ToolHistoryError(LLMProviderError):
    """Raised when message history violates OpenAI/Anthropic tool call integrity."""
    def __init__(self, message: str, details: Dict[str, Any] | None = None):
        super().__init__(
            code="INVALID_TOOL_HISTORY",
            message=message,
            provider="",
            retryable=False,
            status_code=400,
            details=details or {},
        )


def has_tool_results(messages: List[Dict[str, Any]]) -> bool:
    """Return True if message history contains any tool results."""
    return any(msg.get("role") == "tool" for msg in messages)


def validate_tool_history(messages: List[Dict[str, Any]]) -> None:
    """Validate message history structure for OpenAI-compatible tool call rules.

    Raises ToolHistoryError if:
    - Assistant tool call is missing an ID or name.
    - Duplicate tool call IDs exist.
    - Tool result has no tool_call_id or is an orphan (not matching an assistant call).
    - Pending tool calls are not resolved before a new user message or at the end of history.
    """
    pending: Dict[str, Dict[str, Any]] = {}

    for idx, message in enumerate(messages):
        role = message.get("role")

        if role == "assistant":
            tool_calls = message.get("tool_calls") or []
            for tool_call in tool_calls:
                call_id = tool_call.get("id")
                if not call_id:
                    raise ToolHistoryError(
                        f"Assistant tool call at index {idx} is missing an 'id'",
                        details={"index": idx, "tool_call": tool_call},
                    )
                name = tool_call.get("name") or (tool_call.get("function", {}).get("name") if isinstance(tool_call.get("function"), dict) else "")
                if not name:
                    raise ToolHistoryError(
                        f"Assistant tool call '{call_id}' at index {idx} is missing a tool name",
                        details={"index": idx, "call_id": call_id},
                    )
                if call_id in pending:
                    raise ToolHistoryError(
                        f"Duplicate tool call id: {call_id}",
                        details={"call_id": call_id, "index": idx},
                    )
                pending[call_id] = tool_call

        elif role == "tool":
            call_id = message.get("tool_call_id") or message.get("id")
            if not call_id:
                raise ToolHistoryError(
                    f"Tool result at index {idx} is missing 'tool_call_id'",
                    details={"index": idx, "message": message},
                )
            if call_id not in pending:
                raise ToolHistoryError(
                    f"Orphan tool result for call_id '{call_id}' at index {idx}",
                    details={"call_id": call_id, "index": idx},
                )
            del pending[call_id]

        elif role == "user":
            if pending:
                raise ToolHistoryError(
                    f"Pending tool calls {list(pending.keys())} before user message at index {idx}",
                    details={"pending": list(pending.keys()), "index": idx},
                )

    if pending:
        raise ToolHistoryError(
            f"Missing tool results for pending tool calls: {list(pending.keys())}",
            details={"pending": list(pending.keys())},
        )


def clean_tool_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean legacy, duplicate, or orphaned tool calls/results in-place to prevent API errors."""
    # Pass 1: Collect all resolved tool call IDs (those that have a corresponding tool result message)
    resolved_ids = set()
    for message in messages:
        if message.get("role") == "tool":
            call_id = message.get("tool_call_id") or message.get("id")
            if call_id:
                resolved_ids.add(call_id)

    cleaned_messages = []
    for message in messages:
        # copy message dict to avoid mutating original session history
        msg_copy = dict(message)
        role = msg_copy.get("role")

        if role == "assistant":
            tool_calls = msg_copy.get("tool_calls") or []
            valid_calls = []
            for tool_call in tool_calls:
                call_id = tool_call.get("id")
                if not call_id:
                    continue
                name = tool_call.get("name") or (tool_call.get("function", {}).get("name") if isinstance(tool_call.get("function"), dict) else "")
                if not name:
                    continue
                # Only keep the tool call if it has a matching tool result in the history
                if call_id in resolved_ids:
                    valid_calls.append(tool_call)
            if valid_calls:
                msg_copy["tool_calls"] = valid_calls
            else:
                msg_copy.pop("tool_calls", None)

        elif role == "tool":
            call_id = msg_copy.get("tool_call_id") or msg_copy.get("id")
            if not call_id or call_id not in resolved_ids:
                # Skip orphaned tool result
                continue

        cleaned_messages.append(msg_copy)

    # Filter out empty assistant calls with no text and no tool calls
    final_messages = []
    for msg in cleaned_messages:
        if msg.get("role") == "assistant" and not (msg.get("content") or "").strip() and not msg.get("tool_calls"):
            continue
        final_messages.append(msg)

    return final_messages


