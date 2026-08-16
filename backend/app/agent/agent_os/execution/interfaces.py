from abc import ABC, abstractmethod
from typing import Any


class ISandbox(ABC):
    """Execution sandbox container lifecycle interface."""
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def run_command(self, cmd: str) -> dict[str, Any]:
        pass


class IExecutionEngine(ABC):
    """Agent action execution runtime engine."""
    @abstractmethod
    def execute_action(self, action_type: str, payload: Any) -> Any:
        pass


class ITransaction(ABC):
    """Transactional file modification block supporting rollback."""
    @abstractmethod
    def begin(self) -> None:
        pass

    @abstractmethod
    def apply_patch(self, file_path: str, target_content: str, replacement_content: str) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass


class ITransactionalExecutionEngine(ABC):
    """Transactional execution runtime engine that validates and applies patches."""
    @abstractmethod
    def create_transaction(self) -> ITransaction:
        pass

    @abstractmethod
    def validate_patch(self, file_path: str, current_content: str, target_content: str, replacement_content: str) -> str:
        """Validates syntax, conflict detection, and formatting. Returns the patched code on success."""


class IFileLockManager(ABC):
    """File Lock Manager interface to coordinate concurrent file access between agents."""
    @abstractmethod
    def acquire_lock(self, file_path: str, agent_name: str, exclusive: bool = True) -> bool:
        pass

    @abstractmethod
    def release_lock(self, file_path: str, agent_name: str) -> bool:
        pass

    @abstractmethod
    def is_locked(self, file_path: str) -> bool:
        pass

