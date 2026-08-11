"""
Provider Registry — Manages instantiation of adapters from config.
"""

from __future__ import annotations

from typing import Dict, List, Type, Optional, Any

from agent_os.providers.base import ModelProvider, ProviderConfig
from agent_os.providers.common_adapter import CommonAdapter, AnthropicAdapter
from agent_os.providers.configs.providers import PROVIDER_PRESETS


class ProviderRegistry:
    """Registry of available LLM providers and adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[str, Type[ModelProvider]] = {
            "openai": CommonAdapter,
            "anthropic": AnthropicAdapter,
            "gemini": CommonAdapter,
            "groq": CommonAdapter,
            "openrouter": CommonAdapter,
            "ollama": CommonAdapter,
        }

    def create(self, provider_name: str, model: str, api_key: Optional[str] = None, **kwargs: Any) -> ModelProvider:
        """Create a ModelProvider instance based on configuration and protocol."""
        provider_name = provider_name.lower()
        
        # Load preset base configuration
        preset = PROVIDER_PRESETS.get(provider_name)
        if not preset:
            # Fallback configuration for custom/unregistered providers
            config = ProviderConfig(
                name=provider_name,
                model=model,
                api_key=api_key,
                base_url=kwargs.get("base_url"),
                protocol=kwargs.get("protocol", "openai"),
            )
        else:
            config = ProviderConfig(
                name=provider_name,
                model=model or preset.model,
                api_key=api_key or preset.api_key,
                base_url=kwargs.get("base_url") or preset.base_url,
                protocol=kwargs.get("protocol") or preset.protocol,
            )

        # Select corresponding adapter class
        adapter_cls = self._adapters.get(config.protocol, CommonAdapter)
        if config.protocol == "anthropic":
            adapter_cls = AnthropicAdapter

        return adapter_cls(config)

    def list_providers(self) -> List[str]:
        """List all supported built-in providers."""
        return list(PROVIDER_PRESETS.keys())


# Global singleton instance
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Get the global ProviderRegistry."""
    return _registry
