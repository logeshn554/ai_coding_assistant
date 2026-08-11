import inspect
from typing import Any, Dict, Callable, Type, TypeVar
from agent_os.core.interfaces import IServiceRegistry

T = TypeVar("T")

class DIContainer:
    """Dependency Injection container assisting automatic resolution and instantiation."""
    def __init__(self, registry: IServiceRegistry) -> None:
        self.registry = registry

    def resolve(self, cls: Type[T]) -> T:
        """Resolves the type using registry, falling back to constructor auto-wiring."""
        try:
            # 1. Attempt lookup from registered services
            return self.registry.resolve(cls)
        except ValueError:
            # 2. Fall back to constructor signature auto-wiring
            return self.instantiate(cls)

    def instantiate(self, cls: Type[T]) -> T:
        """Instantiates a class, auto-wiring its constructor parameters via DI."""
        if not inspect.isclass(cls):
            raise TypeError(f"Target {cls} is not a class.")

        # If __init__ is default or missing, call constructor directly
        if cls.__init__ == object.__init__:
            return cls()

        sig = inspect.signature(cls.__init__)
        params = list(sig.parameters.values())[1:]  # Skip 'self'
        
        args = {}
        for param in params:
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                raise ValueError(f"Cannot resolve constructor parameter '{param.name}' without type annotation in {cls.__name__}")
            
            # Resolve dependency for parameter
            dependency = self.resolve(param_type)
            args[param.name] = dependency

        return cls(**args)
