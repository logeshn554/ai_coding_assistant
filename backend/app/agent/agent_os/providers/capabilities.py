"""
Model Capabilities — Defines capabilities supported by different models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelCapabilities:
    """Represents capabilities and token limits of a specific model."""
    streaming: bool
    tool_calling: bool
    structured_output: bool
    vision: bool
    reasoning: bool
    max_context_tokens: int


# Default model capabilities mapping
MODEL_CAPABILITIES_MAP = {
    # Anthropic
    "claude-3-5-sonnet": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=True, reasoning=True, max_context_tokens=200000
    ),
    "claude-3-opus": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=False, vision=True, reasoning=True, max_context_tokens=200000
    ),
    "claude-3-haiku": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=False, vision=True, reasoning=False, max_context_tokens=200000
    ),
    # OpenAI
    "gpt-4o": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=True, reasoning=True, max_context_tokens=128000
    ),
    "gpt-4o-mini": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=True, reasoning=False, max_context_tokens=128000
    ),
    "o3-mini": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=False, reasoning=True, max_context_tokens=200000
    ),
    # Gemini
    "gemini-1.5-pro": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=True, reasoning=True, max_context_tokens=1000000
    ),
    "gemini-1.5-flash": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=True, reasoning=False, max_context_tokens=1000000
    ),
    # DeepSeek / OpenRouter / Groq / Ollama defaults
    "deepseek-coder": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=True, vision=False, reasoning=True, max_context_tokens=64000
    ),
    "llama3": ModelCapabilities(
        streaming=True, tool_calling=True, structured_output=False, vision=False, reasoning=False, max_context_tokens=8192
    ),
}

DEFAULT_CAPABILITIES = ModelCapabilities(
    streaming=True, tool_calling=True, structured_output=False, vision=False, reasoning=False, max_context_tokens=8192
)


def get_model_capabilities(model_name: str) -> ModelCapabilities:
    """Resolve ModelCapabilities for a given model name, falling back to default."""
    model_lower = model_name.lower()
    for key, cap in MODEL_CAPABILITIES_MAP.items():
        if key in model_lower:
            return cap
    return DEFAULT_CAPABILITIES
