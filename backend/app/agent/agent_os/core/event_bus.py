import inspect
import asyncio
from typing import Any, Callable, Dict, List, Set, Coroutine
from agent_os.core.interfaces import IEventBus

class EventBus(IEventBus):
    """Asynchronous/Synchronous Event Bus implementation."""
    def __init__(self) -> None:
        self._handlers: Dict[str, Set[Callable[[Any], Any]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Any], Coroutine[Any, Any, None] | None]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = set()
        self._handlers[event_type].add(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], Coroutine[Any, Any, None] | None]) -> None:
        if event_type in self._handlers:
            self._handlers[event_type].discard(handler)

    async def publish(self, event_type: str, data: Any) -> None:
        if event_type not in self._handlers:
            return
        
        # Dispatch to all registered handlers
        tasks = []
        for handler in list(self._handlers[event_type]):
            try:
                if inspect.iscoroutinefunction(handler):
                    tasks.append(asyncio.create_task(handler(data)))
                else:
                    # Run sync handlers directly on loop thread safely (or execute directly if desired)
                    handler(data)
            except Exception as e:
                # Standardize logging/error isolation
                pass
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
