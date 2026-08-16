"""
Providers Layer — Interfaces, presets, adapters, and ModelRouter.
"""

from __future__ import annotations

from agent_os.providers.base import (
    ModelProvider,
    ModelResponse,
    ProviderCapability,
    ProviderConfig,
    ProviderHealth,
    TokenUsage,
    ToolCall,
)
from agent_os.providers.capabilities import ModelCapabilities, get_model_capabilities
from agent_os.providers.interfaces import IEmbeddingProvider, ILLMProvider, IModelRouter
from agent_os.providers.model_router import ModelRouter
from agent_os.providers.registry import ProviderRegistry, get_registry

__all__ = [
    "IEmbeddingProvider",
    "ILLMProvider",
    "IModelRouter",
    "ModelCapabilities",
    "ModelProvider",
    "ModelResponse",
    "ModelRouter",
    "ProviderCapability",
    "ProviderConfig",
    "ProviderHealth",
    "ProviderRegistry",
    "TokenUsage",
    "ToolCall",
    "get_model_capabilities",
    "get_registry",
]
