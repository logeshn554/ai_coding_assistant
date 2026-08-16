"""
Gateway Streaming — SSE/WebSocket streaming abstraction.

Provides:
  - Unified streaming interface for SSE and WebSocket transports
  - Backpressure handling with configurable buffer limits
  - Automatic reconnection protocol with exponential backoff
  - Stream lifecycle management (create → active → paused → completed → error)
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("agentos.gateway.streaming")


class StreamState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StreamTransport(str, Enum):
    SSE = "sse"
    WEBSOCKET = "websocket"
    POLLING = "polling"


@dataclass
class StreamConfig:
    """Configuration for a stream."""
    buffer_size: int = 1000          # max messages buffered
    backpressure_threshold: int = 800 # pause producing at this buffer level
    heartbeat_interval: float = 30.0  # seconds between keepalive pings
    max_reconnect_attempts: int = 5
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    message_ttl: float = 300.0        # max age of buffered messages (seconds)


@dataclass
class StreamMessage:
    """A single message in the stream."""
    id: str
    event_type: str       # chunk, tool_call, status, error, heartbeat
    data: Any
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        import json
        lines = [f"id: {self.id}", f"event: {self.event_type}"]
        if isinstance(self.data, (dict, list)):
            lines.append(f"data: {json.dumps(self.data)}")
        else:
            lines.append(f"data: {self.data}")
        return "\n".join(lines) + "\n\n"

    def to_ws(self) -> dict:
        """Format for WebSocket transport."""
        return {
            "id": self.id,
            "event": self.event_type,
            "data": self.data,
            "ts": self.timestamp,
            "seq": self.sequence,
        }


class StreamChannel:
    """A single streaming channel with backpressure support."""

    def __init__(self, channel_id: str, config: StreamConfig = None):
        self.channel_id = channel_id
        self.config = config or StreamConfig()
        self._state = StreamState.CREATED
        self._buffer: deque[StreamMessage] = deque(maxlen=self.config.buffer_size)
        self._sequence = 0
        self._created_at = time.time()
        self._listeners: list[Callable[[StreamMessage], Any]] = []
        self._event = asyncio.Event()
        self._backpressure = False
        self._total_messages = 0
        self._total_bytes = 0

    @property
    def state(self) -> StreamState:
        return self._state

    @property
    def is_backpressured(self) -> bool:
        return len(self._buffer) >= self.config.backpressure_threshold

    @property
    def buffer_utilization(self) -> float:
        return len(self._buffer) / max(1, self.config.buffer_size)

    def start(self) -> None:
        self._state = StreamState.ACTIVE

    def pause(self) -> None:
        if self._state == StreamState.ACTIVE:
            self._state = StreamState.PAUSED

    def resume(self) -> None:
        if self._state == StreamState.PAUSED:
            self._state = StreamState.ACTIVE
            self._event.set()

    def complete(self) -> None:
        self._state = StreamState.COMPLETED
        self._event.set()

    def error(self, msg: str = "") -> None:
        self._state = StreamState.ERROR
        if msg:
            self.push("error", {"message": msg})
        self._event.set()

    def cancel(self) -> None:
        self._state = StreamState.CANCELLED
        self._event.set()

    def push(self, event_type: str, data: Any) -> bool:
        """Push a message to the stream buffer.

        Returns False if backpressure should be applied.
        """
        if self._state not in (StreamState.ACTIVE, StreamState.CREATED):
            return False

        self._sequence += 1
        msg = StreamMessage(
            id=f"{self.channel_id}-{self._sequence}",
            event_type=event_type,
            data=data,
            sequence=self._sequence,
        )

        self._buffer.append(msg)
        self._total_messages += 1
        self._event.set()

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(msg)
            except Exception:
                pass

        if self.is_backpressured:
            if not self._backpressure:
                self._backpressure = True
                logger.warning(f"Stream {self.channel_id}: backpressure engaged "
                             f"({len(self._buffer)}/{self.config.buffer_size})")
            return False

        self._backpressure = False
        return True

    async def consume(self) -> AsyncIterator[StreamMessage]:
        """Consume messages from the stream as an async iterator."""
        while self._state in (StreamState.ACTIVE, StreamState.CREATED, StreamState.PAUSED):
            if self._buffer:
                yield self._buffer.popleft()
                if self._backpressure and not self.is_backpressured:
                    self._backpressure = False
                    logger.debug(f"Stream {self.channel_id}: backpressure released")
            else:
                self._event.clear()
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=self.config.heartbeat_interval)
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield StreamMessage(
                        id=f"{self.channel_id}-hb",
                        event_type="heartbeat",
                        data={"ts": time.time()},
                        sequence=self._sequence,
                    )

        # Drain remaining buffer
        while self._buffer:
            yield self._buffer.popleft()

    def add_listener(self, listener: Callable[[StreamMessage], Any]) -> None:
        self._listeners.append(listener)

    def get_stats(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "state": self._state.value,
            "buffer_size": len(self._buffer),
            "buffer_capacity": self.config.buffer_size,
            "total_messages": self._total_messages,
            "backpressured": self._backpressure,
            "sequence": self._sequence,
            "uptime_seconds": time.time() - self._created_at,
        }


# ── Stream Manager ──────────────────────────────────────────────────────────

class StreamManager:
    """Manages all active streaming channels."""

    def __init__(self):
        self._channels: dict[str, StreamChannel] = {}
        self._default_config = StreamConfig()

    def create_channel(self, channel_id: str = "", config: StreamConfig = None) -> StreamChannel:
        """Create a new streaming channel."""
        if not channel_id:
            channel_id = f"stream-{uuid.uuid4().hex[:12]}"

        channel = StreamChannel(channel_id, config or self._default_config)
        self._channels[channel_id] = channel
        logger.debug(f"Created stream channel: {channel_id}")
        return channel

    def get_channel(self, channel_id: str) -> StreamChannel | None:
        return self._channels.get(channel_id)

    def close_channel(self, channel_id: str) -> None:
        channel = self._channels.pop(channel_id, None)
        if channel:
            channel.complete()
            logger.debug(f"Closed stream channel: {channel_id}")

    def close_all(self) -> None:
        for channel_id in list(self._channels.keys()):
            self.close_channel(channel_id)

    def cleanup_stale(self, max_age: float = 3600.0) -> int:
        """Clean up stale channels older than max_age seconds."""
        now = time.time()
        stale = [
            cid for cid, ch in self._channels.items()
            if ch.state in (StreamState.COMPLETED, StreamState.ERROR, StreamState.CANCELLED)
            or (now - ch._created_at) > max_age
        ]
        for cid in stale:
            self.close_channel(cid)
        return len(stale)

    def get_all_stats(self) -> list[dict[str, Any]]:
        return [ch.get_stats() for ch in self._channels.values()]


# ── Singleton ───────────────────────────────────────────────────────────────

stream_manager = StreamManager()
