import threading
from typing import Any, Callable, Dict, Type, TypeVar
from agent_os.core.interfaces import IServiceRegistry

T = TypeVar("T")

class ServiceRegistry(IServiceRegistry):
    """Thread-safe Service Registry supporting singleton and factory registrations.

    All mutations and reads are serialized through a threading.RLock so that
    concurrent access from asyncio executor threads and the main event loop
    cannot corrupt the internal dictionaries.
    """
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._singletons: Dict[Type[Any], Any] = {}
        self._factories: Dict[Type[Any], Callable[[], Any]] = {}

    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        with self._lock:
            if not isinstance(instance, service_type) and not issubclass(type(instance), service_type):
                raise TypeError(f"Instance is not an implementation of service type {service_type.__name__}")
            self._singletons[service_type] = instance

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        with self._lock:
            self._factories[service_type] = factory

    def resolve(self, service_type: Type[T]) -> T:
        with self._lock:
            if service_type in self._singletons:
                return self._singletons[service_type]

            if service_type in self._factories:
                instance = self._factories[service_type]()
                return instance

            raise ValueError(f"Service of type {service_type.__name__} is not registered.")
