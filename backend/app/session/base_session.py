# backend/app/session/base_session.py
"""BaseSession defines the common interface for session implementations.
Both AgentSession (desktop) and WorkerSessionProxy (production) inherit from this class.
It provides abstract methods for sending WebSocket messages and any shared utilities.
"""

import abc
from typing import Any


class BaseSession(abc.ABC):
    """Abstract base class for session handling.

    Subclasses must implement ``send_ws_message`` or supply a ``_send_ws_message_callback``
    which transmits a dict payload to the client (WebSocket or event publisher).
    """

    total_cost_usd: float = 0.0
    wasted_turns: int = 0

    async def send_ws_message(self, message: dict[str, Any]) -> None:
        """Send a message to the UI/WS client.

        Args:
            message: Payload dict to be dispatched.
        """
        cb = getattr(self, "_send_ws_message_callback", None)
        if cb is not None:
            import asyncio
            if asyncio.iscoroutinefunction(cb):
                await cb(message)
            else:
                cb(message)
        else:
            raise NotImplementedError("Subclass must implement send_ws_message or provide _send_ws_message_callback")

    async def emit_text_delta(self, text: str) -> None:
        """Send a streaming text_delta chunk."""
        await self.send_ws_message({"type": "text_delta", "content": text})


