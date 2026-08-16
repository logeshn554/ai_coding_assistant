import asyncio
from collections.abc import Callable

from agent_os.core.interfaces import IEventBus
from agent_os.kernel.interfaces import ITaskStateMachine, ITaskStateObserver


class InvalidTransitionError(Exception):
    pass

class TaskStateMachine(ITaskStateMachine):
    """Task State Machine enforcing transitions, rollbacks, and observer updates."""
    
    # State constants
    NEW = "NEW"
    UNDERSTAND = "UNDERSTAND"
    SEARCH = "SEARCH"
    PLAN = "PLAN"
    EDIT = "EDIT"
    VERIFY = "VERIFY"
    TEST = "TEST"
    REVIEW = "REVIEW"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    ESCALATED = "ESCALATED"

    # Forward transitions mappings
    _FORWARD_TRANSITIONS: dict[str, set[str]] = {
        NEW: {UNDERSTAND, FAILED, CANCELLED, PAUSED, ESCALATED},
        UNDERSTAND: {SEARCH, FAILED, CANCELLED, PAUSED, ESCALATED},
        SEARCH: {PLAN, FAILED, CANCELLED, PAUSED, ESCALATED},
        PLAN: {EDIT, FAILED, CANCELLED, PAUSED, ESCALATED},
        EDIT: {VERIFY, FAILED, CANCELLED, PAUSED, ESCALATED},
        VERIFY: {TEST, FAILED, CANCELLED, PAUSED, ESCALATED},
        TEST: {REVIEW, FAILED, CANCELLED, PAUSED, ESCALATED},
        REVIEW: {DONE, FAILED, CANCELLED, PAUSED, ESCALATED},
        PAUSED: {NEW, UNDERSTAND, SEARCH, PLAN, EDIT, VERIFY, TEST, REVIEW, DONE, FAILED, CANCELLED, ESCALATED},
        ESCALATED: {NEW, UNDERSTAND, SEARCH, PLAN, EDIT, VERIFY, TEST, REVIEW, DONE, FAILED, CANCELLED, PAUSED},
        DONE: set(),
        FAILED: set(),
        CANCELLED: set()
    }

    def __init__(self, initial_state: str = NEW, event_bus: IEventBus | None = None) -> None:
        self._current_state = initial_state
        self.event_bus = event_bus
        self._history: list[str] = []
        self._observers: set[ITaskStateObserver] = set()
        self._listeners: list[Callable[[str, str], None]] = []

    @property
    def current_state(self) -> str:
        return self._current_state

    def add_observer(self, observer: ITaskStateObserver) -> None:
        self._observers.add(observer)

    def remove_observer(self, observer: ITaskStateObserver) -> None:
        self._observers.discard(observer)

    def add_listener(self, callback: Callable[[str, str], None]) -> None:
        self._listeners.append(callback)

    def _notify(self, old_state: str, new_state: str) -> None:
        # Observers
        for observer in self._observers:
            try:
                observer.on_state_transition(old_state, new_state)
            except Exception:
                pass
        # Callback listeners
        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception:
                pass
        # Event Bus integration
        if self.event_bus:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self.event_bus.publish("task_state_changed", {
                        "old_state": old_state,
                        "new_state": new_state
                    }))
            except RuntimeError:
                asyncio.run(self.event_bus.publish("task_state_changed", {
                    "old_state": old_state,
                    "new_state": new_state
                }))

    def transition_to(self, state: str) -> None:
        state = state.upper()
        if state == self._current_state:
            return

        # Check if it's a valid forward transition
        valid_next = self._FORWARD_TRANSITIONS.get(self._current_state, set())
        
        if state in valid_next:
            old = self._current_state
            self._history.append(old)
            self._current_state = state
            self._notify(old, state)
            return

        # Check if it's a historical rollback
        if state in self._history:
            self.rollback_to(state)
            return

        raise InvalidTransitionError(f"Cannot transition from state '{self._current_state}' to state '{state}'")

    def rollback(self) -> None:
        if not self._history:
            raise InvalidTransitionError("No historical states available to rollback.")
        
        old = self._current_state
        target = self._history.pop()
        self._current_state = target
        self._notify(old, target)

    def rollback_to(self, state: str) -> None:
        state = state.upper()
        if state not in self._history:
            raise InvalidTransitionError(f"State '{state}' is not present in transition history: {self._history}")
            
        old = self._current_state
        # Pop history stack until we pop the target state
        while self._history:
            popped = self._history.pop()
            if popped == state:
                self._current_state = state
                self._notify(old, state)
                return
