"""
Base Tool Contract — Abstract definitions for real executable tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """The outcome result of executing a tool."""
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Tool(ABC):
    """Abstract base class that all tool executions must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name slug."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of when/how the tool should be used by the LLM."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema defining arguments acceptable by the tool."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Perform the actual action associated with this tool."""
        pass

    def to_schema(self) -> Dict[str, Any]:
        """Format the tool description and schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
