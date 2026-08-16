"""
Tool System — Base classes, registry, and execution framework.

Every tool the agent can invoke is defined as a ToolDefinition with an
executable function, JSON schema, risk level, and timeout.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("agent_runtime.tools")


class RiskLevel(str, Enum):
    """Risk classification for tool operations."""
    LOW = "low"           # read_file, search, list_directory
    MEDIUM = "medium"     # edit_file, run_tests
    HIGH = "high"         # run_command, delete_file
    CRITICAL = "critical" # git_push, deploy


@dataclass
class ToolResult:
    """Result of executing a tool."""
    success: bool
    output: str
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Complete definition of an executable tool.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description shown to the LLM.
        parameters: JSON Schema for the tool's input parameters.
        executor: Async callable that performs the tool action.
        risk_level: Security classification.
        timeout: Maximum execution time in seconds.
    """
    name: str
    description: str
    parameters: dict[str, Any]
    executor: Callable[..., Coroutine[Any, Any, ToolResult]]
    risk_level: RiskLevel = RiskLevel.LOW
    timeout: float = 30.0

    def to_llm_schema(self) -> dict[str, Any]:
        """Convert to the ToolSchema format expected by the LLM interface."""
        from agent_runtime.llm import ToolSchema
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class ToolRegistry:
    """Central registry mapping tool names to their executable definitions.

    Provides tool discovery, permission checking, and guarded execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool.name in self._tools:
            logger.warning("Tool '%s' is being re-registered (overwritten)", tool.name)
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s (risk=%s, timeout=%.0fs)", tool.name, tool.risk_level.value, tool.timeout)

    def get(self, name: str) -> ToolDefinition | None:
        """Retrieve a tool by name."""
        if isinstance(name, str) and "<|channel|>" in name:
            name = name.split("<|channel|>")[0]
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_llm_schemas(self) -> list:
        """Get all tool schemas formatted for the LLM."""
        return [t.to_llm_schema() for t in self._tools.values()]

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments.

        Enforces timeout and captures errors.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments to pass to the tool executor.

        Returns:
            ToolResult with success/failure, output, and timing.
        """
        if isinstance(tool_name, str) and "<|channel|>" in tool_name:
            tool_name = tool_name.split("<|channel|>")[0]
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' is not registered. Available tools: {list(self._tools.keys())}",
            )

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                tool.executor(**arguments),
                timeout=tool.timeout,
            )
            result.duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "Tool '%s' completed: success=%s, duration=%.0fms",
                tool_name, result.success, result.duration_ms,
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("Tool '%s' timed out after %.0fs", tool_name, tool.timeout)
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' timed out after {tool.timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("Tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' execution error: {type(e).__name__}: {e}",
                duration_ms=duration_ms,
            )
