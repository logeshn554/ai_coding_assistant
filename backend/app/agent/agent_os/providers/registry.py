"""
Provider Registry — Manages instantiation of adapters from config.
"""

from __future__ import annotations

from typing import Any

from agent_os.providers.base import ModelProvider, ProviderConfig
from agent_os.providers.common_adapter import AnthropicAdapter, CommonAdapter
from agent_os.providers.configs.providers import PROVIDER_PRESETS


class ProviderRegistry:
    """Registry of available LLM providers and adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, type[ModelProvider]] = {
            "openai": CommonAdapter,
            "anthropic": AnthropicAdapter,
            "gemini": CommonAdapter,
            "groq": CommonAdapter,
            "openrouter": CommonAdapter,
            "ollama": CommonAdapter,
        }

    def create(self, provider_name: str, model: str, api_key: str | None = None, **kwargs: Any) -> ModelProvider:
        """Create a ModelProvider instance based on configuration and protocol."""
        provider_name = provider_name.lower()
        
        temperature = 1.0
        top_p = 1.0
        max_tokens = 16384
        seed = 42
        stream = True
        try:
            from backend.app.config import config_manager
            temperature = config_manager.get_temperature()
            top_p = config_manager.get_top_p()
            max_tokens = config_manager.get_max_tokens()
            seed = config_manager.get_seed()
            stream = config_manager.get_stream()
        except Exception:
            pass

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
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                seed=seed,
                stream=stream,
            )
        else:
            config = ProviderConfig(
                name=provider_name,
                model=model or preset.model,
                api_key=api_key or preset.api_key,
                base_url=kwargs.get("base_url") or preset.base_url,
                protocol=kwargs.get("protocol") or preset.protocol,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                seed=seed,
                stream=stream,
            )

        # Select corresponding adapter class
        adapter_cls = self._adapters.get(config.protocol, CommonAdapter)
        if config.protocol == "anthropic":
            adapter_cls = AnthropicAdapter

        return adapter_cls(config)

    def list_providers(self) -> list[str]:
        """List all supported built-in providers."""
        return list(PROVIDER_PRESETS.keys())


# Global singleton instance
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Get the global ProviderRegistry."""
    return _registry
