from abc import ABC, abstractmethod
from typing import Any
from agent_os.core.interfaces import IServiceRegistry, IEventBus, IConfig, ILogger

class IKernelService(ABC):
    """Lifecycle service managed by the kernel."""
    @abstractmethod
    def on_init(self) -> None:
        pass

    @abstractmethod
    def on_shutdown(self) -> None:
        pass


class IKernel(ABC):
    """Core operating system kernel interface for AgentOS."""
    @property
    @abstractmethod
    def registry(self) -> IServiceRegistry:
        pass

    @property
    @abstractmethod
    def event_bus(self) -> IEventBus:
        pass

    @property
    @abstractmethod
    def config(self) -> IConfig:
        pass

    @property
    @abstractmethod
    def logger(self) -> ILogger:
        pass

    @abstractmethod
    def register_service(self, name: str, service: IKernelService) -> None:
        pass

    @abstractmethod
    def boot(self) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass


class ITaskStateObserver(ABC):
    """Observer pattern interface for tracking Task State changes."""
    @abstractmethod
    def on_state_transition(self, old_state: str, new_state: str) -> None:
        pass


class ITaskStateMachine(ABC):
    """Task Lifecycle State Machine interface."""
    @property
    @abstractmethod
    def current_state(self) -> str:
        pass

    @abstractmethod
    def transition_to(self, state: str) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass

    @abstractmethod
    def rollback_to(self, state: str) -> None:
        pass

    @abstractmethod
    def add_observer(self, observer: ITaskStateObserver) -> None:
        pass

    @abstractmethod
    def remove_observer(self, observer: ITaskStateObserver) -> None:
        pass

    # camelCase compatibility aliases
    def transitionTo(self, state: str) -> None:
        return self.transition_to(state)

    def rollbackTo(self, state: str) -> None:
        return self.rollback_to(state)

    def addObserver(self, observer: ITaskStateObserver) -> None:
        return self.add_observer(observer)

    def removeObserver(self, observer: ITaskStateObserver) -> None:
        return self.remove_observer(observer)

