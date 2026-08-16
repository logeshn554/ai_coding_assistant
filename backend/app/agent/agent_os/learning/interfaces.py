from abc import ABC, abstractmethod
from typing import Any


class IMemoryStore(ABC):
    """Long-term and short-term agent memory storage."""
    @abstractmethod
    def store(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Any:
        pass


class ILearningEngine(ABC):
    """Dynamic retrieval, correction learning, and knowledge items synthesis."""
    @abstractmethod
    def store_fix(self, error_type: str, file_path: str, error_msg: str, solution_diff: str) -> None:
        pass

    @abstractmethod
    def store_summary(self, repo_path: str, summary: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def store_pattern(self, pattern_name: str, pattern_type: str, code_snippet: str) -> None:
        pass

    @abstractmethod
    def store_convention(self, convention_name: str, rule: str) -> None:
        pass

    @abstractmethod
    def store_performance(self, operation: str, duration_sec: float, token_count: int) -> None:
        pass

    @abstractmethod
    def find_similar_fixes(self, query: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def find_similar_patterns(self, query: str) -> list[dict[str, Any]]:
        pass



class IMemoryManager(ABC):
    """Structured AgentOS Memory Manager interface."""
    @abstractmethod
    def set_current_task(self, task: str) -> None:
        pass

    @abstractmethod
    def get_current_task(self) -> str | None:
        pass

    @abstractmethod
    def set_current_plan(self, plan: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_current_plan(self) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def set_repository_state(self, state: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_repository_state(self) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def add_artifact(self, name: str, artifact: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_artifacts(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def add_event(self, event_type: str, payload: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_events(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def set_current_patch(self, patch: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_current_patch(self) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def set_diagnostics(self, diagnostics: list[dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_diagnostics(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def clear_all(self) -> None:
        pass

    @abstractmethod
    def persist_to_disk(self, filepath: str) -> None:
        pass

    @abstractmethod
    def load_from_disk(self, filepath: str) -> None:
        pass


class IPerformanceOptimizer(ABC):
    """Structured Performance Optimizer tracking system stats and generating recommendations."""
    @abstractmethod
    def track_metric(self, name: str, value: float) -> None:
        pass

    @abstractmethod
    def get_recommendations(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def generate_report(self) -> str:
        pass

