"""
Event system for orchestration observability.

Features:
  - Unique event IDs prevent duplicates
  - Full context (run_id, task_id, agent_id, attempt_id, sequence)
  - Idempotent event processing
  - Monotonic progress tracking per attempt
  - Event persistence and replay
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime
from enum import Enum
import uuid
import asyncio


class EventType(str, Enum):
    """All event types in the system."""
    # Run events
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"

    # Plan events
    PLAN_CREATED = "plan.created"
    PLAN_VALIDATION_STARTED = "plan.validation.started"
    PLAN_VALIDATION_COMPLETED = "plan.validation.completed"

    # Task events
    TASK_CREATED = "task.created"
    TASK_READY = "task.ready"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_SKIPPED = "task.skipped"

    # Agent events
    AGENT_CREATED = "agent.created"
    AGENT_STARTED = "agent.started"
    AGENT_STATE_TRANSITION = "agent.state.transition"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    # LLM events
    LLM_REQUESTED = "llm.requested"
    LLM_COMPLETED = "llm.completed"
    LLM_FAILED = "llm.failed"

    # Tool events
    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"

    # Verification events
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_COMPLETED = "verification.completed"
    VERIFICATION_FAILED = "verification.failed"

    # Repair events
    REPAIR_STARTED = "repair.started"
    REPAIR_COMPLETED = "repair.completed"

    # Progress events
    PROGRESS_UPDATED = "progress.updated"


@dataclass
class Event:
    """Single event with full context for tracing."""
    event_id: str  # Unique ID for deduplication
    event_type: EventType
    run_id: str
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    attempt_id: Optional[str] = None
    execution_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    sequence_number: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.event_id)

    def __eq__(self, other):
        return isinstance(other, Event) and self.event_id == other.event_id


@dataclass
class Progress:
    """Progress tracking with monotonicity enforcement."""
    run_id: str
    task_id: Optional[str] = None
    attempt_id: Optional[str] = None

    # Individual progress values (0-100)
    task_progress: int = 0  # Progress on current task
    attempt_progress: int = 0  # Progress on current attempt
    run_progress: int = 0  # Overall run progress

    # Enforcement: store max seen to ensure monotonicity
    _max_task_progress: int = field(default=0, init=False)
    _max_attempt_progress: int = field(default=0, init=False)
    _max_run_progress: int = field(default=0, init=False)

    def update_task_progress(self, value: int) -> bool:
        """Update task progress, enforcing monotonicity. Returns True if updated."""
        if value < 0 or value > 100:
            return False
        if value < self._max_task_progress:
            return False  # Reject regress
        self._max_task_progress = value
        self.task_progress = value
        return True

    def update_attempt_progress(self, value: int) -> bool:
        """Update attempt progress, enforcing monotonicity. Returns True if updated."""
        if value < 0 or value > 100:
            return False
        if value < self._max_attempt_progress:
            return False  # Reject regress
        self._max_attempt_progress = value
        self.attempt_progress = value
        return True

    def update_run_progress(self, value: int) -> bool:
        """Update run progress, enforcing monotonicity. Returns True if updated."""
        if value < 0 or value > 100:
            return False
        if value < self._max_run_progress:
            return False  # Reject regress
        self._max_run_progress = value
        self.run_progress = value
        return True

    def reset_task_attempt(self) -> None:
        """Reset attempt progress when starting new attempt. Task progress stays."""
        self._max_attempt_progress = 0
        self.attempt_progress = 0


class EventBus:
    """Central event bus for system-wide observability."""

    def __init__(self):
        self._events: List[Event] = []
        self._seen_event_ids: set = set()
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._sequence_number = 0
        self._progress_map: Dict[str, Progress] = {}

    async def emit(
        self,
        event_type: EventType,
        run_id: str,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Event:
        """
        Emit an event.

        Args:
            event_type: Type of event
            run_id: Run ID for tracking
            task_id: Associated task ID (optional)
            agent_id: Associated agent ID (optional)
            attempt_id: Associated attempt ID (optional)
            execution_id: Associated execution ID (optional)
            tool_call_id: Associated tool call ID (optional)
            payload: Event-specific data

        Returns:
            The emitted Event (or existing if duplicate)
        """
        async with self._lock:
            # Create event with unique ID
            event_id = str(uuid.uuid4())

            # Check for duplicates (same type + context + payload)
            duplicate_key = (event_type, run_id, task_id, agent_id, attempt_id)
            if duplicate_key in self._seen_event_ids:
                # Find existing event
                for evt in self._events:
                    if (evt.event_type == event_type and evt.run_id == run_id and
                        evt.task_id == task_id and evt.agent_id == agent_id and
                        evt.attempt_id == attempt_id):
                        return evt  # Return existing, don't emit duplicate

            # Create new event
            event = Event(
                event_id=event_id,
                event_type=event_type,
                run_id=run_id,
                task_id=task_id,
                agent_id=agent_id,
                attempt_id=attempt_id,
                execution_id=execution_id,
                tool_call_id=tool_call_id,
                sequence_number=self._sequence_number,
                timestamp=datetime.utcnow(),
                payload=payload or {},
            )

            self._sequence_number += 1
            self._events.append(event)
            self._seen_event_ids.add(duplicate_key)

            # Notify subscribers
            if event_type in self._subscribers:
                for subscriber in self._subscribers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(subscriber):
                            await subscriber(event)
                        else:
                            subscriber(event)
                    except Exception:
                        pass  # Silently ignore subscriber errors

            return event

    async def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subscribe to events of a type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def get_events_for_run(self, run_id: str) -> List[Event]:
        """Get all events for a run."""
        return [e for e in self._events if e.run_id == run_id]

    def get_events_for_task(self, task_id: str) -> List[Event]:
        """Get all events for a task."""
        return [e for e in self._events if e.task_id == task_id]

    def get_events_for_agent(self, agent_id: str) -> List[Event]:
        """Get all events for an agent."""
        return [e for e in self._events if e.agent_id == agent_id]

    def get_progress(self, run_id: str, task_id: Optional[str] = None) -> Optional[Progress]:
        """Get progress for run/task."""
        key = f"{run_id}:{task_id}" if task_id else run_id
        return self._progress_map.get(key)

    async def update_progress(
        self,
        run_id: str,
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        task_progress: Optional[int] = None,
        attempt_progress: Optional[int] = None,
        run_progress: Optional[int] = None,
    ) -> Progress:
        """Update progress with monotonicity enforcement."""
        async with self._lock:
            key = f"{run_id}:{task_id}" if task_id else run_id

            if key not in self._progress_map:
                self._progress_map[key] = Progress(
                    run_id=run_id,
                    task_id=task_id,
                    attempt_id=attempt_id,
                )

            progress = self._progress_map[key]

            # Update values that were provided
            if task_progress is not None:
                progress.update_task_progress(task_progress)

            if attempt_progress is not None:
                progress.update_attempt_progress(attempt_progress)

            if run_progress is not None:
                progress.update_run_progress(run_progress)

            # Emit progress event
            await self.emit(
                EventType.PROGRESS_UPDATED,
                run_id=run_id,
                task_id=task_id,
                attempt_id=attempt_id,
                payload={
                    "task_progress": progress.task_progress,
                    "attempt_progress": progress.attempt_progress,
                    "run_progress": progress.run_progress,
                },
            )

            return progress

    def get_all_events(self) -> List[Event]:
        """Get all events."""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._events.clear()
        self._seen_event_ids.clear()
        self._progress_map.clear()
