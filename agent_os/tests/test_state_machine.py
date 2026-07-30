import asyncio
import pytest
from agent_os.kernel.state_machine import TaskStateMachine, InvalidTransitionError
from agent_os.kernel.interfaces import ITaskStateObserver
from agent_os.core.event_bus import EventBus

class DummyObserver(ITaskStateObserver):
    def __init__(self) -> None:
        self.transitions = []

    def on_state_transition(self, old_state: str, new_state: str) -> None:
        self.transitions.append((old_state, new_state))

def test_state_machine_sequential_progression():
    sm = TaskStateMachine()
    assert sm.current_state == TaskStateMachine.NEW

    # NEW -> UNDERSTAND
    sm.transition_to(TaskStateMachine.UNDERSTAND)
    assert sm.current_state == TaskStateMachine.UNDERSTAND

    # UNDERSTAND -> SEARCH -> PLAN -> EDIT
    sm.transition_to(TaskStateMachine.SEARCH)
    sm.transition_to(TaskStateMachine.PLAN)
    sm.transition_to(TaskStateMachine.EDIT)
    assert sm.current_state == TaskStateMachine.EDIT

    # Verify invalid jump raises error
    with pytest.raises(InvalidTransitionError):
        sm.transition_to(TaskStateMachine.DONE)

def test_state_machine_rollbacks():
    sm = TaskStateMachine()
    sm.transition_to(TaskStateMachine.UNDERSTAND)
    sm.transition_to(TaskStateMachine.SEARCH)
    sm.transition_to(TaskStateMachine.PLAN)

    # Rollback last state (PLAN -> SEARCH)
    sm.rollback()
    assert sm.current_state == TaskStateMachine.SEARCH

    # Rollback further (SEARCH -> UNDERSTAND)
    sm.rollback()
    assert sm.current_state == TaskStateMachine.UNDERSTAND

    # Multi-step rollback: go back to plan then edit
    sm.transition_to(TaskStateMachine.SEARCH)
    sm.transition_to(TaskStateMachine.PLAN)
    sm.transition_to(TaskStateMachine.EDIT)
    
    # Rollback to UNDERSTAND
    sm.rollback_to(TaskStateMachine.UNDERSTAND)
    assert sm.current_state == TaskStateMachine.UNDERSTAND

    # Rollback to nonexistent state raises error
    with pytest.raises(InvalidTransitionError):
        sm.rollback_to("NONEXISTENT")

@pytest.mark.asyncio
async def test_state_machine_observers_and_events():
    event_bus = EventBus()
    sm = TaskStateMachine(event_bus=event_bus)

    # 1. Test interface observer
    observer = DummyObserver()
    sm.add_observer(observer)

    # 2. Test callback listener
    callbacks = []
    sm.add_listener(lambda old, new: callbacks.append((old, new)))

    # 3. Test event bus subscriber
    eb_events = []
    event_bus.subscribe("task_state_changed", lambda payload: eb_events.append(payload))

    # Trigger transition
    sm.transition_to(TaskStateMachine.UNDERSTAND)
    await asyncio.sleep(0.005)

    # Verify observer
    assert len(observer.transitions) == 1
    assert observer.transitions[0] == (TaskStateMachine.NEW, TaskStateMachine.UNDERSTAND)

    # Verify callback
    assert len(callbacks) == 1
    assert callbacks[0] == (TaskStateMachine.NEW, TaskStateMachine.UNDERSTAND)

    # Verify event bus
    assert len(eb_events) == 1
    assert eb_events[0]["old_state"] == TaskStateMachine.NEW
    assert eb_events[0]["new_state"] == TaskStateMachine.UNDERSTAND

    # Remove observer and verify no new notifications are sent to it
    sm.remove_observer(observer)
    sm.transition_to(TaskStateMachine.SEARCH)
    await asyncio.sleep(0.005)
    
    assert len(observer.transitions) == 1
    assert len(callbacks) == 2
