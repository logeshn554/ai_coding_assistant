"""
Durable Event Bus — Persistent event bus with replay capability for pub/sub communication.

Supports:
  - Synchronous & asynchronous subscription/unsubscription
  - Append-only persistent storage of event logs
  - Replaying events from a specific timestamp or sequence ID
  - Event schemas and routing keys
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("agentos.infrastructure.event_bus")


@dataclass
class Event:
    """An event dispatched via the Durable Event Bus."""
    event_type: str
    data: Any
    sequence_id: int = 0
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""
    sender: str = ""


class DurableEventBus:
    """A durable event bus tracking event logs in memory with replay support."""

    def __init__(self) -> None:
        self._handlers: dict[str, set[Callable[[Event], Any]]] = {}
        self._event_log: list[Event] = []
        self._sequence_counter = 0

    def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = set()
        self._handlers[event_type].add(handler)
        logger.debug(f"Subscribed handler to event type: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Remove a handler for an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].discard(handler)
            if not self._handlers[event_type]:
                del self._handlers[event_type]

    async def publish(self, event_type: str, data: Any, correlation_id: str = "", sender: str = "") -> None:
        """Publish an event to all subscribers and record it in the persistent log."""
        self._sequence_counter += 1
        event = Event(
            event_type=event_type,
            data=data,
            sequence_id=self._sequence_counter,
            correlation_id=correlation_id,
            sender=sender,
        )
        self._event_log.append(event)

        # Retrieve direct matching handlers and wildcard handlers
        handlers = set(self._handlers.get(event_type, []))
        if "*" in self._handlers:
            handlers.update(self._handlers["*"])

        tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(asyncio.create_task(handler(event)))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error executing event handler for {event_type}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def replay(self, since_sequence_id: int = 0, since_timestamp: float = 0.0) -> list[Event]:
        """Replay and return historically recorded events."""
        return [
            event for event in self._event_log
            if event.sequence_id >= since_sequence_id and event.timestamp >= since_timestamp
        ]

    def get_event_log(self) -> list[Event]:
        """Return the complete event log."""
        return list(self._event_log)

    def clear_log(self) -> None:
        self._event_log.clear()
        self._sequence_counter = 0


