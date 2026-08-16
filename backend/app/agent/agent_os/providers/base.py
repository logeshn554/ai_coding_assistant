"""
Base Provider Contracts — Data classes and interfaces for LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderCapability(str, Enum):
    """Supported model capabilities."""
    STREAMING = "streaming"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STRUCTURED_OUTPUT = "structured_output"
    LONG_CONTEXT = "long_context"


@dataclass
class ToolCall:
    """Represents a tool use request from the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    """Detailed token consumption statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ModelResponse:
    """Normalized response format across all model providers."""
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    model: str = ""
    provider: str = ""


@dataclass
class ProviderHealth:
    """Health check outcome for a provider connection."""
    healthy: bool
    latency_ms: float
    error: str | None = None


@dataclass
class ProviderConfig:
    """Generic configuration schema for any adapter."""
    name: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    protocol: str = "openai"  # "openai" or "anthropic"
    timeout: float = 60.0
    temperature: float = 0.0
    max_tokens: int = 4096
    top_p: float = 1.0
    seed: int | None = None
    stream: bool = True


class ModelProvider(ABC):
    """Abstract contract that all model adapters must implement."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Execute single request/response loop."""

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Stream chunks of responses as an async generator."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Determine if provider can connect and verify API keys."""
