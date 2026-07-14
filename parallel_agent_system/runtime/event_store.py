import os
import json
import asyncio
from typing import AsyncGenerator

import redis.asyncio as aioredis
from parallel_agent_system.runtime.agent_runtime import Event


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

def get_redis_client():
    """Returns the global active Redis client (or mock/fallback client)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    import sys
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    # For testing, check if running inside pytest or if mock redis is configured
    is_testing = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
    
    if redis_url.startswith("mock://") or os.environ.get("MOCK_REDIS", "false").lower() == "true" or is_testing:
        _redis_client = MemoryRedisStream
    else:
        try:
            # Create real async redis client
            _redis_client = aioredis.from_url(redis_url, decode_responses=False)
        except Exception:
            _redis_client = MemoryRedisStream
    return _redis_client


def deserialize_event(json_str: str) -> Event:
    """Polymorphically deserializes Event JSON strings into ActionEvent, ObservationEvent, or base Event."""
    try:
        data = json.loads(json_str)
    except Exception:
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
    """

    def __init__(self, run_id: str, subtask_id: str):
        self.run_id = run_id
        self.subtask_id = subtask_id
        self.key = f"events:{run_id}:{subtask_id}"
        self.client = get_redis_client()

    async def append(self, event: Event) -> None:
        """Appends a new Event to the Redis Stream."""
        data = {"data": event.model_dump_json()}
        if self.client is MemoryRedisStream:
            await MemoryRedisStream.xadd(self.key, data)
        else:
            await self.client.xadd(self.key, data)

    async def tail(self, last_id: str = "0") -> AsyncGenerator[Event, None]:
        """Tails the EventLog stream in real time."""
        if self.client is MemoryRedisStream:
            async for item in MemoryRedisStream.tail(self.key):
                yield deserialize_event(item["data"])
        else:
            # Tail real Redis stream
            current_id = last_id
            while True:
                try:
                    # Block for up to 500ms
                    response = await self.client.xread({self.key: current_id}, block=500, count=10)
                    if response:
                        for _, entries in response:
                            for msg_id, data in entries:
                                current_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                                json_data = data[b"data"].decode() if b"data" in data else data["data"]
                                yield deserialize_event(json_data)
                except Exception:
                    # Backoff on error
                    await asyncio.sleep(0.5)
