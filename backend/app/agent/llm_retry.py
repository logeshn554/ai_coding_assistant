"""
LLM Retry & Tool Idempotency Controller — Tracks completed tool call results to ensure
tool operations are never re-executed due to LLM transport or continuation timeouts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("devpilot.agent.llm_retry")


@dataclass
class ToolExecutionRecord:
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    status: str
    result: Any
    error: str = ""


class ToolIdempotencyRegistry:
    """Tracks completed tool executions per session to prevent duplicate execution during retries."""

    def __init__(self) -> None:
        self._records: dict[str, ToolExecutionRecord] = {}

    def record_execution(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        status: str,
        result: Any,
        error: str = "",
    ) -> None:
        """Store finished tool execution record."""
        if not tool_call_id:
            return
        self._records[tool_call_id] = ToolExecutionRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=arguments,
            status=status,
            result=result,
            error=error,
        )

    def get_completed_record(self, tool_call_id: str) -> ToolExecutionRecord | None:
        """Retrieve completed record if tool was already executed."""
        return self._records.get(tool_call_id)

    def is_completed(self, tool_call_id: str) -> bool:
        """Check if tool call ID was already completed."""
        return tool_call_id in self._records

    def clear(self) -> None:
        """Clear registry."""
        self._records.clear()
