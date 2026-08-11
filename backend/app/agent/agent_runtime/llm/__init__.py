"""
LLM Provider Interface — Abstract contract for all model providers.

Every provider (OpenAI, Anthropic, Gemini, etc.) implements this interface
so the agent loop can call any model through a uniform API.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional


@dataclass
class ToolCallRequest:
    """A tool call requested by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from a single LLM generation call."""
    content: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"  # "stop", "tool_calls", "length", "error"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_final(self) -> bool:
        return self.finish_reason == "stop" and not self.has_tool_calls


@dataclass
class LLMChunk:
    """A single chunk from a streaming LLM response."""
    content: str = ""
    tool_call_delta: Optional[dict[str, Any]] = None
    finish_reason: Optional[str] = None


@dataclass
class Message:
    """A single message in the conversation history."""
    role: str  # "system", "user", "assistant", "tool"
    content: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_call_id: Optional[str] = None  # For tool result messages
    name: Optional[str] = None  # Tool name for tool result messages

    def to_dict(self) -> dict[str, Any]:
        """Convert to provider-agnostic dict format."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass
class ToolSchema:
    """JSON Schema definition for a tool, passed to the LLM."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    Subclasses must implement ``generate`` and optionally ``stream``.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send messages to the model and receive a complete response.

        Args:
            messages: Conversation history.
            tools: Available tool definitions for function calling.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Stream response chunks from the model.

        Default implementation falls back to ``generate`` and yields the
        full response as a single chunk.
        """
        response = await self.generate(messages, tools, temperature, max_tokens)
        yield LLMChunk(content=response.content, finish_reason=response.finish_reason)

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and healthy."""
        ...
