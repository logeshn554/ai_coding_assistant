"""# reference implementation — not wired into production"""

import time
import asyncio
from typing import AsyncGenerator, Dict, List, Set, Any
from agent_os.providers.interfaces import IModelRouter

class RateLimitError(Exception):
    pass

class ProviderError(Exception):
    pass

class ModelRouter(IModelRouter):
    """Architectural Model Router handling capabilities routing, dynamic fallbacks, retries, and rate limits."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 0.01, rpm_limit: int = 10) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.rpm_limit = rpm_limit
        
        # Provider health configuration
        self._provider_health: Dict[str, bool] = {
            "anthropic": True,
            "openai": True,
            "gemini": True,
            "groq": True,
            "ollama": True
        }
        
        # Priority list for fallback routing
        self._fallback_order = ["anthropic", "openai", "gemini", "groq", "ollama"]
        
        # Request timestamps for rate limiting
        self._request_timestamps: List[float] = []
        self._cancelled_tasks: Set[str] = set()

    def health_check(self, provider_name: str) -> bool:
        return self._provider_health.get(provider_name.lower(), False)

    def set_provider_health(self, provider_name: str, healthy: bool) -> None:
        self._provider_health[provider_name.lower()] = healthy

    def cancel(self, task_id: str) -> None:
        self._cancelled_tasks.add(task_id)

    def _check_rate_limit(self) -> None:
        """Enforces a sliding-window Rate Limiter (Requests Per Minute)."""
        now = time.time()
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]
        if len(self._request_timestamps) >= self.rpm_limit:
            raise RateLimitError("Rate limit exceeded. Too many requests per minute.")
        self._request_timestamps.append(now)

    def _select_providers(self, model_name: str) -> List[str]:
        """Resolves target and fallback provider sequence based on requested model name/feature."""
        model_name = model_name.lower()
        if "claude" in model_name or "anthropic" in model_name:
            primary = "anthropic"
        elif "gpt" in model_name or "openai" in model_name:
            primary = "openai"
        elif "gemini" in model_name:
            primary = "gemini"
        elif "groq" in model_name:
            primary = "groq"
        elif "ollama" in model_name:
            primary = "ollama"
        else:
            primary = "anthropic"

        providers = [primary]
        for fallback in self._fallback_order:
            if fallback != primary and self.health_check(fallback):
                providers.append(fallback)
        return providers

    async def generate(self, prompt: str, system_prompt: str = "", model_name: str = "default") -> str:
        providers = self._select_providers(model_name)
        last_error = None

        for provider in providers:
            if not self.health_check(provider):
                continue

            for attempt in range(self.max_retries):
                try:
                    self._check_rate_limit()
                    
                    # Simulate API execution
                    res = await self._mock_provider_call(provider, prompt)
                    return res
                except RateLimitError as e:
                    last_error = e
                    # For rate limit, back off and retry
                    await asyncio.sleep(self.base_delay * (2 ** attempt))
                except Exception as e:
                    last_error = e
                    # For provider failure, back off and retry
                    await asyncio.sleep(self.base_delay * (2 ** attempt))

            # Mark provider as unhealthy on retry exhaustions to trigger fallbacks
            self.set_provider_health(provider, False)

        raise ProviderError(f"All routed model providers failed or rate-limited. Last error: {str(last_error)}")

    async def _mock_provider_call(self, provider: str, prompt: str) -> str:
        """Simulates provider completions."""
        if not self.health_check(provider):
            raise ConnectionError(f"Connection failed for provider: {provider}")
        return f"[{provider.upper()} RESPONSE] for prompt: {prompt}"

    async def stream(self, prompt: str, system_prompt: str = "", model_name: str = "default") -> AsyncGenerator[str, None]:
        response = await self.generate(prompt, system_prompt, model_name)
        words = response.split(" ")
        for i, word in enumerate(words):
            yield (word + " " if i < len(words) - 1 else word)
            await asyncio.sleep(0.001)
