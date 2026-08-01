import os
import json
import asyncio
import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis
from parallel_agent_system.runtime.agent_runtime import Event

logger = logging.getLogger("parallel_agent_system.event_store")


class MemoryRedisStream:
    """In-memory Redis stream fallback to support offline testing and mock operations."""

    _streams: dict[str, list[dict]] = {}
    _listeners: dict[str, list[asyncio.Queue]] = {}

    @classmethod
    async def xadd(cls, key: str, data: dict) -> str:
        cls._streams.setdefault(key, []).append(data)

        # Notify active tail listeners
        if key in cls._listeners:
            for queue in cls._listeners[key]:
                await queue.put(data)
        return "1-0"

    @classmethod
    async def tail(cls, key: str) -> AsyncGenerator[dict, None]:
        queue = asyncio.Queue()
        cls._listeners.setdefault(key, []).append(queue)

        # Yield existing items first
        for item in cls._streams.get(key, []):
            yield item

        try:
            while True:
                item = await queue.get()
                yield item
        finally:
            if key in cls._listeners and queue in cls._listeners[key]:
                cls._listeners[key].remove(queue)


# --- Redis Connection Helper ---

_redis_client = None
_using_memory_fallback = False


def get_redis_client():
    """Returns the global active Redis client (or mock/fallback client)."""
    global _redis_client, _using_memory_fallback
    if _redis_client is not None:
        return _redis_client

    import sys
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    # For testing, check if running inside pytest or if mock redis is configured
    is_testing = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)

    if redis_url.startswith("mock://") or os.environ.get("MOCK_REDIS", "false").lower() == "true" or is_testing:
        _redis_client = MemoryRedisStream
        _using_memory_fallback = True
    else:
        try:
            # Create real async redis client
            _redis_client = aioredis.from_url(redis_url, decode_responses=False)
            _using_memory_fallback = False
        except Exception as exc:
            logger.warning(
                "Failed to create Redis client for event store (%s); "
                "falling back to MemoryRedisStream: %s",
                redis_url,
                exc,
            )
            _redis_client = MemoryRedisStream
            _using_memory_fallback = True
    return _redis_client


def _force_memory_fallback(reason: Exception | str) -> None:
    """Switch the global client to MemoryRedisStream after a Redis failure."""
    global _redis_client, _using_memory_fallback
    if _using_memory_fallback and _redis_client is MemoryRedisStream:
        return
    logger.warning(
        "Redis event store operation failed; falling back to MemoryRedisStream + asyncio.Queue: %s",
        reason,
    )
    _redis_client = MemoryRedisStream
    _using_memory_fallback = True


def deserialize_event(json_str: str) -> Event:
    """Polymorphically deserializes Event JSON strings into ActionEvent, ObservationEvent, or base Event."""
    try:
        data = json.loads(json_str)
    except Exception as exc:
        logger.debug("Failed to deserialize event JSON: %s", exc)
        return Event()

    if "action" in data:
        from parallel_agent_system.runtime.agent_runtime import ActionEvent
        return ActionEvent.model_validate(data)
    elif "observation" in data:
        from parallel_agent_system.runtime.agent_runtime import ObservationEvent
        return ObservationEvent.model_validate(data)
    else:
        return Event.model_validate(data)


# --- Event Store ---

class RedisEventStore:
    """
    Bridges OpenHands EventLog stream directly to Redis Streams.
    Provides real-time pub/sub tail capabilities for WebSocket streaming.
    Falls back to MemoryRedisStream + asyncio.Queue when Redis is unavailable.
    """

    def __init__(self, run_id: str, subtask_id: str, attempt: int = 1):
        self.run_id = run_id
        self.subtask_id = subtask_id
        self.attempt = attempt
        self.key = f"events:{run_id}:{subtask_id}:{attempt}"
        self.client = get_redis_client()

    def _refresh_client(self):
        """Refresh the client reference after a possible fallback switch."""
        self.client = get_redis_client()

    async def append(self, event: Event) -> None:
        """Appends a new Event to the Redis Stream (or in-memory fallback)."""
        data = {"data": event.model_dump_json()}
        self._refresh_client()
        if self.client is MemoryRedisStream:
            await MemoryRedisStream.xadd(self.key, data)
            return
        try:
            await self.client.xadd(self.key, data)
        except Exception as exc:
            _force_memory_fallback(exc)
            self._refresh_client()
            await MemoryRedisStream.xadd(self.key, data)

    async def tail(self, last_id: str = "0") -> AsyncGenerator[Event, None]:
        """Tails the EventLog stream in real time."""
        self._refresh_client()
        if self.client is MemoryRedisStream:
            async for item in MemoryRedisStream.tail(self.key):
                yield deserialize_event(item["data"])
            return

        # Tail real Redis stream; fall back mid-stream on persistent failure.
        current_id = last_id
        consecutive_failures = 0
        while True:
            try:
                self._refresh_client()
                if self.client is MemoryRedisStream:
                    async for item in MemoryRedisStream.tail(self.key):
                        yield deserialize_event(item["data"])
                    return

                # Block for up to 500ms
                response = await self.client.xread({self.key: current_id}, block=500, count=10)
                consecutive_failures = 0
                if response:
                    for _, entries in response:
                        for msg_id, data in entries:
                            current_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                            json_data = data[b"data"].decode() if b"data" in data else data["data"]
                            yield deserialize_event(json_data)
            except Exception as exc:
                consecutive_failures += 1
                logger.warning(
                    "RedisEventStore.tail error (attempt %s): %s",
                    consecutive_failures,
                    exc,
                )
                if consecutive_failures >= 3:
                    _force_memory_fallback(exc)
                    self._refresh_client()
                    async for item in MemoryRedisStream.tail(self.key):
                        yield deserialize_event(item["data"])
                    return
                await asyncio.sleep(0.5)
