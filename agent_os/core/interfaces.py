from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Type, TypeVar

T = TypeVar("T")

class ILogger(ABC):
    """Standardized logger interface for AgentOS."""
    @abstractmethod
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass


class IConfig(ABC):
    """Configuration management interface."""
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def get_typed(self, type_cls: Type[T], key: str, default: Any = None) -> T:
        pass

    @abstractmethod
    def update(self, key: str, value: Any) -> None:
        pass


class IEventBus(ABC):
    """Event Bus interface for pub/sub communication."""
    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[Any], Coroutine[Any, Any, None] | None]) -> None:
        pass

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: Callable[[Any], Coroutine[Any, Any, None] | None]) -> None:
        pass

    @abstractmethod
    async def publish(self, event_type: str, data: Any) -> None:
        pass


class IServiceRegistry(ABC):
    """Service locator registry interface."""
    @abstractmethod
    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        pass

    @abstractmethod
    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        pass

    @abstractmethod
    def resolve(self, service_type: Type[T]) -> T:
        pass
