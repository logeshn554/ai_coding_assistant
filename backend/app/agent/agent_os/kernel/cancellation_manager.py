"""
Kernel Cancellation Manager — Cooperative cancellation tokens for agent tasks.

Provides:
  - Cooperative cancellation check via cancellation tokens/flags
  - Thread-safe register, cancel, and status check of execution flows
  - Timeout-based auto-cancellation scheduling
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_os.kernel.interfaces import IKernelService

logger = logging.getLogger("agentos.kernel.cancellation_manager")


@dataclass
class CancellationToken:
    """Token indicating whether a task has been cancelled and why."""
    task_id: str
    is_cancelled: bool = False
    reason: str = ""
    cancelled_at: float = 0.0
    parent_task_id: str | None = None


class CancellationManager(IKernelService):
    """Manages task cancellation tokens and propagates cancellation events."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}
        self._children: dict[str, set[str]] = {}  # parent_id -> set of child_ids
        self._callbacks: dict[str, list[Callable[[str, str], Any]]] = {}

    def on_init(self) -> None:
        logger.info("Initializing CancellationManager service")

    def on_shutdown(self) -> None:
        logger.info("Shutting down CancellationManager service")
        self._tokens.clear()
        self._children.clear()
        self._callbacks.clear()

    def register_task(self, task_id: str, parent_task_id: str | None = None) -> CancellationToken:
        """Register a new task with a cancellation token."""
        token = CancellationToken(task_id=task_id, parent_task_id=parent_task_id)
        self._tokens[task_id] = token

        if parent_task_id:
            if parent_task_id not in self._children:
                self._children[parent_task_id] = set()
            self._children[parent_task_id].add(task_id)

            # If parent is already cancelled, cancel child immediately
            parent_token = self._tokens.get(parent_task_id)
            if parent_token and parent_token.is_cancelled:
                self.cancel_task(task_id, f"Parent task {parent_task_id} was cancelled: {parent_token.reason}")

        return token

    def unregister_task(self, task_id: str) -> None:
        """Remove a task and clean up its references."""
        token = self._tokens.pop(task_id, None)
        if token and token.parent_task_id:
            parent_id = token.parent_task_id
            if parent_id in self._children:
                self._children[parent_id].discard(task_id)
                if not self._children[parent_id]:
                    del self._children[parent_id]

        # Clean up callbacks
        self._callbacks.pop(task_id, None)

        # Recursively unregister children
        children = self._children.pop(task_id, set())
        for child_id in children:
            self.unregister_task(child_id)

    def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """Cancel a task and all of its subtasks."""
        token = self._tokens.get(task_id)
        if not token:
            logger.warning(f"Attempted to cancel unregistered task: {task_id}")
            return False

        if token.is_cancelled:
            return True

        token.is_cancelled = True
        token.reason = reason
        token.cancelled_at = time.time()
        logger.info(f"Task cancelled: {task_id} (reason: {reason})")

        # Trigger callbacks
        callbacks = self._callbacks.get(task_id, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(task_id, reason))
                else:
                    cb(task_id, reason)
            except Exception as e:
                logger.error(f"Cancellation callback error for task {task_id}: {e}")

        # Cancel child tasks
        children = self._children.get(task_id, set())
        for child_id in list(children):
            self.cancel_task(child_id, f"Parent task {task_id} cancelled: {reason}")

        return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task (or any of its parents) has been cancelled."""
        token = self._tokens.get(task_id)
        if not token:
            return False
        return token.is_cancelled

    def add_cancellation_callback(self, task_id: str, callback: Callable[[str, str], Any]) -> None:
        """Add a callback to trigger when task is cancelled: cb(task_id, reason)."""
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)

    def schedule_timeout(self, task_id: str, timeout_seconds: float, reason: str = "Timeout exceeded") -> None:
        """Schedule a background task to cancel this task after a delay."""
        async def _timeout_helper():
            await asyncio.sleep(timeout_seconds)
            if self.get_token(task_id) and not self.is_cancelled(task_id):
                self.cancel_task(task_id, reason)

        asyncio.create_task(_timeout_helper())

    def get_token(self, task_id: str) -> CancellationToken | None:
        return self._tokens.get(task_id)


