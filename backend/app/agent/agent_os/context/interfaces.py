from abc import ABC, abstractmethod
from typing import Any


class IContextEngine(ABC):
    """Semantic context modeling and token/prompt budgeting."""
    @abstractmethod
    def build_excerpt(self, path: str, query: str) -> str:
        pass

    @abstractmethod
    def allocate_budget(self, sizes: dict[str, int]) -> dict[str, int]:
        pass


class IContextManager(ABC):
    """Context selection, token aggregation, and Virtual Memory paging."""
    @abstractmethod
    def add_to_context(self, name: str, data: Any) -> None:
        pass

    @abstractmethod
    def get_prompt_payload(self) -> str:
        pass

    @abstractmethod
    def load_context(self, key: str, content: str, level: str) -> None:
        pass

    @abstractmethod
    def promote(self, key: str) -> None:
        pass

    @abstractmethod
    def demote(self, key: str) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def estimate_tokens(self, key: str | None = None) -> int:
        pass

    # camelCase compatibility aliases
    def loadContext(self, key: str, content: str, level: str) -> None:
        return self.load_context(key, content, level)

    def estimateTokens(self, key: str | None = None) -> int:
        return self.estimate_tokens(key)
