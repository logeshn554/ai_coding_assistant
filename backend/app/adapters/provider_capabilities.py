"""
Provider Capabilities Engine — Defines model/provider feature support including
streaming tool continuation policies for NVIDIA and OpenAI-compatible endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    """Explicit capabilities supported by an LLM provider and model instance."""
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_streaming_tool_calls: bool = True
    supports_streaming_tool_continuation: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False
    context_window: int = 128_000
    max_output_tokens: int = 8_192


def get_provider_capabilities(provider: str = "", base_url: str = "", model_name: str = "") -> ProviderCapabilities:
    """Resolve capability policy for given provider, base_url, and model."""
    url_lower = (base_url or "").lower()
    prov_lower = (provider or "").lower()
    model_lower = (model_name or "").lower()

    # NVIDIA OpenAI-compatible API endpoint policy
    if "integrate.api.nvidia.com" in url_lower or prov_lower == "nvidia" or "nvidia/" in model_lower:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_streaming_tool_calls=True,
            supports_streaming_tool_continuation=False,  # NVIDIA policy: non-streaming continuation after tool result
            supports_vision=False,
            supports_reasoning=False,
            context_window=128_000,
            max_output_tokens=4_096,
        )

    # Standard OpenAI / Anthropic default capabilities
    return ProviderCapabilities(
        supports_streaming=True,
        supports_tools=True,
        supports_streaming_tool_calls=True,
        supports_streaming_tool_continuation=True,
        supports_vision="vision" in model_lower or "4o" in model_lower or "claude-3" in model_lower,
        supports_reasoning="o1" in model_lower or "o3" in model_lower or "r1" in model_lower,
        context_window=128_000,
        max_output_tokens=8_192,
    )
