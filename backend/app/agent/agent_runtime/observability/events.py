"""
Production Observability & Tracing — Canonical event schemas and event sourcing.

Provides a unified event structure and a thread-safe EventTracer to track
exactly why agents run, what tools they execute, and details of their failures.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from pydantic import BaseModel, Field


class CanonicalEvent(BaseModel):
    """The unified event structure for the coding assistant runtime."""
    event_id: str = Field(description="Unique UUID for this event")
    run_id: str = Field(description="Identifies the execution run session")
    task_id: str | None = Field(None, description="Active task ID in the DAG")
    agent_id: str | None = Field(None, description="The agent instance ID")
    attempt_id: int = Field(1, description="Iteration or retry attempt number")
    event_type: str = Field(
        description="Type of event (e.g. 'run.started', 'llm.request', 'tool.executed', 'verify.completed')"
    )
    timestamp: float = Field(default_factory=time.time)
    payload: dict[str, Any] = Field(default_factory=dict, description="Event-specific metadata")
    sequence: int = Field(0, description="Sequential ordering number in the run trace")


class EventTracer:
    """Thread-safe event tracer that records execution histories.

    Supports querying, filtering, and exporting traces to JSON files for reproducibility.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[CanonicalEvent] = []
        self._sequences: dict[str, int] = defaultdict(int)

    def record(
        self,
        run_id: str,
        event_type: str,
        task_id: str | None = None,
        agent_id: str | None = None,
        attempt_id: int = 1,
        payload: dict[str, Any] | None = None,
    ) -> CanonicalEvent:
        """Create and persist a new canonical event trace."""
        import uuid

        with self._lock:
            seq = self._sequences[run_id]
            self._sequences[run_id] += 1

            event = CanonicalEvent(
                event_id=str(uuid.uuid4()),
                run_id=run_id,
                task_id=task_id,
                agent_id=agent_id,
                attempt_id=attempt_id,
                event_type=event_type,
                timestamp=time.time(),
                payload=payload or {},
                sequence=seq,
            )
            self._events.append(event)
            return event

    def get_run_trace(self, run_id: str) -> list[CanonicalEvent]:
        """Retrieve all events sorted by sequence number for a specific run."""
        with self._lock:
            return sorted(
                [e for e in self._events if e.run_id == run_id],
                key=lambda e: e.sequence
            )

    def get_task_trace(self, run_id: str, task_id: str) -> list[CanonicalEvent]:
        """Retrieve all events related to a specific task inside a run."""
        with self._lock:
            return sorted(
                [e for e in self._events if e.run_id == run_id and e.task_id == task_id],
                key=lambda e: e.sequence
            )

    def export_json(self, run_id: str, file_path: str) -> None:
        """Save a run's event trace to a JSON file for analysis."""
        trace = self.get_run_trace(run_id)
        data = [t.model_dump() for t in trace]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, default=str)


from collections import defaultdict
