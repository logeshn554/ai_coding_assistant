import os
from typing import Any, TypeVar

from agent_os.core.interfaces import IConfig

T = TypeVar("T")

class DictionaryConfig(IConfig):
    """Simple configuration implementation loading dictionary state with environment overrides."""
    def __init__(self, initial_config: dict[str, Any] | None = None):
        self._config: dict[str, Any] = initial_config or {}

    def get(self, key: str, default: Any = None) -> Any:
        # Check environment first
        env_val = os.getenv(key)
        if env_val is not None:
            return env_val
        return self._config.get(key, default)

    def get_typed(self, type_cls: type[T], key: str, default: Any = None) -> T:
        raw_val = self.get(key, default)
        if raw_val is None:
            return None
        
        # Safe type conversions
        if type_cls is bool:
            if isinstance(raw_val, str):
                return raw_val.lower() in ("true", "1", "yes", "on")
            return bool(raw_val)
        
        try:
            return type_cls(raw_val)
        except (ValueError, TypeError):
            if default is not None:
                return type_cls(default)
            raise

    def update(self, key: str, value: Any) -> None:
        self._config[key] = value
