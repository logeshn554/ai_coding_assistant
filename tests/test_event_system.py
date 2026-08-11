"""
Tests for event system and progress tracking (Phase 2b-2c).
"""

import pytest
import asyncio

from agent_os.agent import EventBus, EventType, Progress


class TestEventBus:
    """Test event bus functionality."""

    @pytest.mark.asyncio
    async def test_emit_event(self):
        """Test emitting an event."""
        bus = EventBus()

        event = await bus.emit(
            EventType.TASK_STARTED,
            run_id="run-1",
            task_id="task-1",
            payload={"status": "starting"}
        )

        assert event is not None
        assert event.event_type == EventType.TASK_STARTED
        assert event.run_id == "run-1"
        assert event.task_id == "task-1"
        assert event.payload["status"] == "starting"

    @pytest.mark.asyncio
    async def test_duplicate_event_prevention(self):
        """Test that duplicate events are not emitted twice."""
        bus = EventBus()

        # Emit first event
        event1 = await bus.emit(
            EventType.TASK_COMPLETED,
            run_id="run-1",
            task_id="task-1",
            payload={"result": "success"}
        )

        # Emit what looks like the same event
        event2 = await bus.emit(
            EventType.TASK_COMPLETED,
            run_id="run-1",
            task_id="task-1",
            payload={"result": "success"}
        )

        # Should return the same event
        assert event1.event_id == event2.event_id

        # Should only have one event in history
        all_events = bus.get_all_events()
        task_completed_events = [e for e in all_events if e.event_type == EventType.TASK_COMPLETED]
        assert len(task_completed_events) == 1

    @pytest.mark.asyncio
    async def test_get_events_for_run(self):
        """Test retrieving events for a specific run."""
        bus = EventBus()

        # Emit events for different runs
        await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t1")
        await bus.emit(EventType.TASK_STARTED, run_id="run-2", task_id="t2")
        await bus.emit(EventType.TASK_COMPLETED, run_id="run-1", task_id="t1")

        # Get events for run-1
        run1_events = bus.get_events_for_run("run-1")
        assert len(run1_events) == 2
        assert all(e.run_id == "run-1" for e in run1_events)

        # Get events for run-2
        run2_events = bus.get_events_for_run("run-2")
        assert len(run2_events) == 1
        assert all(e.run_id == "run-2" for e in run2_events)

    @pytest.mark.asyncio
    async def test_get_events_for_task(self):
        """Test retrieving events for a specific task."""
        bus = EventBus()

        await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t1")
        await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t2")
        await bus.emit(EventType.TASK_COMPLETED, run_id="run-1", task_id="t1")

        # Get events for task t1
        t1_events = bus.get_events_for_task("t1")
        assert len(t1_events) == 2
        assert all(e.task_id == "t1" for e in t1_events)

    @pytest.mark.asyncio
    async def test_get_events_for_agent(self):
        """Test retrieving events for a specific agent."""
        bus = EventBus()

        await bus.emit(EventType.AGENT_STARTED, run_id="run-1", agent_id="agent-1")
        await bus.emit(EventType.AGENT_STARTED, run_id="run-1", agent_id="agent-2")
        await bus.emit(EventType.AGENT_COMPLETED, run_id="run-1", agent_id="agent-1")

        # Get events for agent-1
        agent1_events = bus.get_events_for_agent("agent-1")
        assert len(agent1_events) == 2
        assert all(e.agent_id == "agent-1" for e in agent1_events)

    @pytest.mark.asyncio
    async def test_subscriber_notification(self):
        """Test that subscribers are notified of events."""
        bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        await bus.subscribe(EventType.TASK_COMPLETED, handler)

        await bus.emit(EventType.TASK_COMPLETED, run_id="run-1", task_id="t1")
        await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t1")

        # Only TASK_COMPLETED should have been received
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.TASK_COMPLETED


class TestProgress:
    """Test progress tracking with monotonicity enforcement."""

    def test_progress_monotonicity_task(self):
        """Test that task progress is monotonic."""
        progress = Progress(run_id="run-1")

        # Should accept increasing values
        assert progress.update_task_progress(10)
        assert progress.task_progress == 10

        assert progress.update_task_progress(50)
        assert progress.task_progress == 50

        # Should reject regressing values
        assert not progress.update_task_progress(30)
        assert progress.task_progress == 50  # Unchanged

    def test_progress_monotonicity_attempt(self):
        """Test that attempt progress is monotonic."""
        progress = Progress(run_id="run-1")

        assert progress.update_attempt_progress(20)
        assert progress.attempt_progress == 20

        assert progress.update_attempt_progress(80)
        assert progress.attempt_progress == 80

        # Reject regress
        assert not progress.update_attempt_progress(60)
        assert progress.attempt_progress == 80

    def test_progress_monotonicity_run(self):
        """Test that run progress is monotonic."""
        progress = Progress(run_id="run-1")

        assert progress.update_run_progress(5)
        assert progress.run_progress == 5

        assert progress.update_run_progress(100)
        assert progress.run_progress == 100

        # Reject regress
        assert not progress.update_run_progress(50)
        assert progress.run_progress == 100

    def test_progress_invalid_values(self):
        """Test that invalid progress values are rejected."""
        progress = Progress(run_id="run-1")

        # Negative values
        assert not progress.update_task_progress(-1)

        # Values > 100
        assert not progress.update_task_progress(101)

        # Valid value
        assert progress.update_task_progress(50)

    def test_progress_reset_attempt(self):
        """Test resetting attempt progress for new attempt."""
        progress = Progress(run_id="run-1", attempt_id="attempt-1")

        # Set attempt progress
        progress.update_attempt_progress(50)
        assert progress.attempt_progress == 50

        # Reset for new attempt
        progress.reset_task_attempt()
        assert progress.attempt_progress == 0

        # Should be able to set again
        assert progress.update_attempt_progress(30)
        assert progress.attempt_progress == 30


class TestEventBusProgress:
    """Test event bus with progress tracking."""

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test updating progress via event bus."""
        bus = EventBus()

        progress = await bus.update_progress(
            run_id="run-1",
            task_id="task-1",
            task_progress=25,
            run_progress=10
        )

        assert progress.task_progress == 25
        assert progress.run_progress == 10

        # Check that progress event was emitted
        events = bus.get_events_for_task("task-1")
        progress_events = [e for e in events if e.event_type == EventType.PROGRESS_UPDATED]
        assert len(progress_events) > 0

    @pytest.mark.asyncio
    async def test_progress_monotonicity_in_bus(self):
        """Test that bus enforces progress monotonicity."""
        bus = EventBus()

        # Update to 50
        p1 = await bus.update_progress(
            run_id="run-1",
            task_id="task-1",
            task_progress=50
        )
        assert p1.task_progress == 50

        # Update to 75 (should work)
        p2 = await bus.update_progress(
            run_id="run-1",
            task_id="task-1",
            task_progress=75
        )
        assert p2.task_progress == 75

        # Try to update to 30 (should be rejected)
        p3 = await bus.update_progress(
            run_id="run-1",
            task_id="task-1",
            task_progress=30
        )
        # Progress object should return same one with unchanged value
        assert p3.task_progress == 75

    @pytest.mark.asyncio
    async def test_get_progress(self):
        """Test retrieving progress."""
        bus = EventBus()

        await bus.update_progress(
            run_id="run-1",
            task_id="task-1",
            task_progress=50
        )

        progress = bus.get_progress("run-1", "task-1")
        assert progress is not None
        assert progress.task_progress == 50


class TestEventSequencing:
    """Test event sequencing and ordering."""

    @pytest.mark.asyncio
    async def test_event_sequence_numbers(self):
        """Test that events have monotonically increasing sequence numbers."""
        bus = EventBus()

        event1 = await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t1")
        event2 = await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t2")
        event3 = await bus.emit(EventType.TASK_COMPLETED, run_id="run-1", task_id="t1")

        assert event1.sequence_number < event2.sequence_number < event3.sequence_number

    @pytest.mark.asyncio
    async def test_event_timestamps(self):
        """Test that events have timestamps."""
        bus = EventBus()

        event1 = await bus.emit(EventType.TASK_STARTED, run_id="run-1", task_id="t1")
        await asyncio.sleep(0.01)  # Small delay
        event2 = await bus.emit(EventType.TASK_COMPLETED, run_id="run-1", task_id="t1")

        assert event1.timestamp <= event2.timestamp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
