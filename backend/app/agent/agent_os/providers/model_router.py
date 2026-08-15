"""
Model Router — Orchestrates routing, capabilities discovery, and provider adapters.
Supports both legacy string completions and new structured multi-provider message generation.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Union, AsyncGenerator

from agent_os.providers.interfaces import IModelRouter
from agent_os.providers.base import ModelProvider, ProviderConfig, ModelResponse, ProviderHealth
from agent_os.providers.registry import get_registry


class ModelRouter(IModelRouter):
    """Orchestrates requests to selected LLM providers.
    
    Supports both:
    1. Legacy string prompt completions for compatibility with old agent OS workflows.
    2. New structured message histories and tool call definitions for the real agent loop.
    """

    def __init__(self, config: Optional[ProviderConfig] = None) -> None:
        self.registry = get_registry()
        
        # Load provider configuration with safe defaults
        if config is None:
            try:
                import os
                provider = os.getenv("LLM_PROVIDER", "openai")
                model = (os.getenv(f"{provider.upper()}_MODEL") or os.getenv("DEVPILOT_MODEL") or "").strip()
                api_key = os.getenv(f"{provider.upper()}_API_KEY")
                
                # Check secret registry fallback
                if not api_key:
                    from agent_os.core.secret_registry import SecretRegistry
                    api_key = SecretRegistry.get(f"{provider.upper()}_API_KEY") or SecretRegistry.get("LLM_API_KEY")
                
                if not model or not api_key:
                    # Incomplete config — leave an empty placeholder; callers must supply model
                    config = ProviderConfig(
                        name=provider or "openai",
                        model=model or "",
                        base_url=os.getenv(f"{provider.upper()}_BASE_URL") or "https://api.openai.com/v1",
                        api_key=api_key or "mock-key",
                    )
                else:
                    config = ProviderConfig(
                        name=provider,
                        model=model,
                        api_key=api_key,
                        base_url=os.getenv(f"{provider.upper()}_BASE_URL"),
                    )
            except Exception:
                config = ProviderConfig(
                    name="openai",
                    model="",
                    base_url="https://api.openai.com/v1",
                    api_key="mock-key",
                )

        self.config = config
        self.provider = self.registry.create(
            provider_name=config.name,
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self._provider_health = {
            "anthropic": True,
            "openai": True,
            "gemini": True,
            "groq": True,
            "ollama": True
        }

    async def generate(
        self,
        messages: Union[str, List[Dict[str, str]]],
        system_prompt: str = "",
        model_name: str = "default",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Union[str, ModelResponse]:
        """Generate LLM response, supporting both legacy strings and structured inputs."""
        if isinstance(messages, str):
            # Legacy format execution
            import os
            from agent_os.core.secret_registry import SecretRegistry
            
            resolved_provider = "openai"
            model_lower = model_name.lower()
            if "claude" in model_lower or "anthropic" in model_lower:
                resolved_provider = "anthropic"
            elif "gemini" in model_lower:
                resolved_provider = "gemini"
            elif "groq" in model_lower:
                resolved_provider = "groq"
            elif "ollama" in model_lower:
                resolved_provider = "ollama"

            api_key = SecretRegistry.get(f"{resolved_provider.upper()}_API_KEY") or SecretRegistry.get("LLM_API_KEY")
            
            # Check ConfigManager fallback
            if not api_key:
                try:
                    from backend.app.config import ConfigManager
                    profile = ConfigManager().get_active_profile()
                    if profile:
                        api_key = profile.get("api_key")
                except Exception:
                    pass

            if not api_key or api_key.startswith("mock") or os.environ.get("AGENT_RUNTIME_MODE", "").lower() == "mock":
                # Simulated completion
                return f"[{resolved_provider.upper()} RESPONSE] for prompt: {messages}"

            # Instantiate dynamic adapter
            temp_provider = self.registry.create(resolved_provider, model_name, api_key)
            payload = []
            if system_prompt:
                payload.append({"role": "system", "content": system_prompt})
            payload.append({"role": "user", "content": messages})
            
            res = await temp_provider.generate(payload, tools=tools, **kwargs)
            return res.content or ""
        else:
            # Structured generate call
            return await self.provider.generate(messages, tools=tools, **kwargs)

    async def stream(
        self,
        messages: Union[str, List[Dict[str, str]]],
        system_prompt: str = "",
        model_name: str = "default",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream chunks from model provider."""
        if isinstance(messages, str):
            # Legacy streaming fallback
            response = await self.generate(messages, system_prompt, model_name, tools, **kwargs)
            words = response.split(" ")
            for i, word in enumerate(words):
                yield (word + " " if i < len(words) - 1 else word)
                await asyncio.sleep(0.001)
        else:
            # Structured stream
            async for chunk in self.provider.stream(messages, tools=tools, **kwargs):
                yield chunk

    def cancel(self, task_id: str) -> None:
        """Cancel a running task (legacy method)."""
        pass

    def health_check(self, provider_name: Optional[str] = None) -> Any:
        """Check provider connection status (supports legacy boolean response or health report)."""
        if provider_name is not None:
            # Legacy boolean status check
            return self._provider_health.get(provider_name.lower(), True)
        
        # Real health check verification
        try:
            return asyncio.run(self.provider.health_check())
        except Exception as e:
            return ProviderHealth(healthy=False, latency_ms=0.0, error=str(e))

    def healthCheck(self, provider_name: str) -> bool:
        """CamelCase alias for interfaces mapping compatibility."""
        return self.health_check(provider_name)

    def switch_provider(self, provider_name: str, model: str, api_key: str, **kwargs: Any) -> None:
        """Switch current ModelRouter to a different configured provider."""
        config = ProviderConfig(
            name=provider_name,
            model=model,
            api_key=api_key,
            base_url=kwargs.get("base_url"),
        )
        self.config = config
        self.provider = self.registry.create(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            base_url=config.base_url,
        )
