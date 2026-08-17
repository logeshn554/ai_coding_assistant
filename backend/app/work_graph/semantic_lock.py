"""
Semantic Lock — Manages symbol-level and file-level locks to prevent merge conflicts during parallel executions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("loopix.work_graph.semantic_lock")


@dataclass
class LockInfo:
    owner_task_id: str
    acquired_at: float


class SemanticLock:
    """Provides granular mutual exclusion over workspace source files and code symbols."""

    def __init__(self) -> None:
        self._locks: dict[str, LockInfo] = {}

    def acquire_lock(self, resource_uri: str, owner_task_id: str) -> bool:
        """Attempt to acquire a write lock on a resource (file or symbol)."""
        import time
        existing = self._locks.get(resource_uri)
        if existing:
            if existing.owner_task_id == owner_task_id:
                return True
            logger.warning(
                f"Resource conflict: '{resource_uri}' is already locked "
                f"by task '{existing.owner_task_id}'"
            )
            return False

        self._locks[resource_uri] = LockInfo(owner_task_id=owner_task_id, acquired_at=time.time())
        logger.debug(f"Lock acquired on '{resource_uri}' by task '{owner_task_id}'")
        return True

    def release_lock(self, resource_uri: str, owner_task_id: str) -> bool:
        """Release a write lock if owned by the caller."""
        existing = self._locks.get(resource_uri)
        if not existing:
            return True

        if existing.owner_task_id != owner_task_id:
            logger.error(
                f"Lock violation: Task '{owner_task_id}' tried to release lock "
                f"on '{resource_uri}' owned by '{existing.owner_task_id}'"
            )
            return False

        del self._locks[resource_uri]
        logger.debug(f"Lock released on '{resource_uri}' by task '{owner_task_id}'")
        return True

    def get_lock_owner(self, resource_uri: str) -> str | None:
        info = self._locks.get(resource_uri)
        return info.owner_task_id if info else None

    def clear(self) -> None:
        self._locks.clear()


# ── Singleton ───────────────────────────────────────────────────────────────

semantic_lock = SemanticLock()
