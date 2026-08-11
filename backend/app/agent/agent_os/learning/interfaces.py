from abc import ABC, abstractmethod
from typing import Any, List, Dict

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
    def store_summary(self, repo_path: str, summary: Dict[str, Any]) -> None:
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
    def find_similar_fixes(self, query: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_similar_patterns(self, query: str) -> List[Dict[str, Any]]:
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
    def set_current_plan(self, plan: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_current_plan(self) -> Dict[str, Any] | None:
        pass

    @abstractmethod
    def set_repository_state(self, state: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_repository_state(self) -> Dict[str, Any] | None:
        pass

    @abstractmethod
    def add_artifact(self, name: str, artifact: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_artifacts(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def add_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_events(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def set_current_patch(self, patch: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_current_patch(self) -> Dict[str, Any] | None:
        pass

    @abstractmethod
    def set_diagnostics(self, diagnostics: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_diagnostics(self) -> List[Dict[str, Any]]:
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
    def get_recommendations(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def generate_report(self) -> str:
        pass

