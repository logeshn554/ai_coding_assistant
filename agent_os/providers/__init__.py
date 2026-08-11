"""
Providers Layer — Interfaces, presets, adapters, and ModelRouter.
"""

from __future__ import annotations

from agent_os.providers.interfaces import ILLMProvider, IEmbeddingProvider, IModelRouter
from agent_os.providers.base import (
    ProviderCapability,
    ToolCall,
    TokenUsage,
    ModelResponse,
    ProviderHealth,
    ModelProvider,
    ProviderConfig,
)
from agent_os.providers.capabilities import ModelCapabilities, get_model_capabilities
from agent_os.providers.registry import ProviderRegistry, get_registry
from agent_os.providers.model_router import ModelRouter

__all__ = [
    "ILLMProvider",
    "IEmbeddingProvider",
    "IModelRouter",
    "ModelRouter",
    "ProviderCapability",
    "ToolCall",
    "TokenUsage",
    "ModelResponse",
    "ProviderHealth",
    "ModelProvider",
    "ProviderConfig",
    "ModelCapabilities",
    "get_model_capabilities",
    "ProviderRegistry",
    "get_registry",
]
