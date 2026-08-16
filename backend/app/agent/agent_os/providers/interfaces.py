from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


class ILLMProvider(ABC):
    """Model LLM provider abstraction."""
    @abstractmethod
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        pass

    @abstractmethod
    def stream_complete(self, prompt: str, system_prompt: str = "") -> Any:
        pass


class IEmbeddingProvider(ABC):
    """Text vector representations embedding provider interface."""
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        pass


class IModelRouter(ABC):
    """Model Routing Core interface supporting fallbacks, retries, and rate limits."""
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "", model_name: str = "default") -> str:
        pass

    @abstractmethod
    def stream(self, prompt: str, system_prompt: str = "", model_name: str = "default") -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    def cancel(self, task_id: str) -> None:
        pass

    @abstractmethod
    def health_check(self, provider_name: str) -> bool:
        pass

    # camelCase compatibility alias
    def healthCheck(self, provider_name: str) -> bool:
        return self.health_check(provider_name)
