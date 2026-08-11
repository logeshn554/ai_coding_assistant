"""
Agent state machine with validated transitions.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from .interfaces import AgentState, IAgentStateManager


# Valid state transitions (from -> to)
VALID_TRANSITIONS: Dict[AgentState, List[AgentState]] = {
    AgentState.CREATED: [AgentState.INITIALIZING, AgentState.CANCELLED],
    AgentState.INITIALIZING: [AgentState.PLANNING, AgentState.FAILED, AgentState.CANCELLED],
    AgentState.PLANNING: [AgentState.READY, AgentState.FAILED, AgentState.CANCELLED],
    AgentState.READY: [AgentState.RUNNING, AgentState.BLOCKED, AgentState.CANCELLED],
    AgentState.RUNNING: [
        AgentState.WAITING_FOR_LLM,
        AgentState.VERIFYING,
        AgentState.BLOCKED,
        AgentState.TIMEOUT,
        AgentState.CANCELLED,
        AgentState.BUDGET_EXCEEDED,
    ],
    AgentState.WAITING_FOR_LLM: [
        AgentState.WAITING_FOR_TOOL,
        AgentState.VERIFYING,
        AgentState.FAILED,
        AgentState.TIMEOUT,
        AgentState.CANCELLED,
        AgentState.BUDGET_EXCEEDED,
    ],
    AgentState.WAITING_FOR_TOOL: [AgentState.EXECUTING_TOOL, AgentState.CANCELLED, AgentState.TIMEOUT],
    AgentState.EXECUTING_TOOL: [
        AgentState.OBSERVING,
        AgentState.FAILED,
        AgentState.TIMEOUT,
        AgentState.CANCELLED,
    ],
    AgentState.OBSERVING: [
        AgentState.RUNNING,
        AgentState.VERIFYING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    ],
    AgentState.VERIFYING: [
        AgentState.COMPLETED,
        AgentState.REPAIRING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    ],
    AgentState.REPAIRING: [
        AgentState.RUNNING,
        AgentState.RETRYING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    ],
    AgentState.RETRYING: [
        AgentState.RUNNING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    ],
    AgentState.COMPLETED: [AgentState.CANCELLED],  # Terminal, only cancel possible
    AgentState.FAILED: [AgentState.CANCELLED],  # Terminal
    AgentState.BLOCKED: [AgentState.RUNNING, AgentState.FAILED, AgentState.CANCELLED],
    AgentState.CANCELLED: [],  # Terminal
    AgentState.TIMEOUT: [AgentState.RETRYING, AgentState.FAILED, AgentState.CANCELLED],
    AgentState.BUDGET_EXCEEDED: [],  # Terminal
}

# Terminal states (no transitions out)
TERMINAL_STATES = {
    AgentState.COMPLETED,
    AgentState.FAILED,
    AgentState.CANCELLED,
    AgentState.BUDGET_EXCEEDED,
}


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime
    reason: Optional[str] = None


class AgentStateMachine(IAgentStateManager):
    """Validates state transitions per the agent lifecycle."""

    def __init__(self, initial_state: AgentState = AgentState.CREATED):
        self._current_state = initial_state
        self._history: List[StateTransition] = [
            StateTransition(None, initial_state, datetime.utcnow(), "initial")
        ]
        self._lock = asyncio.Lock()

    @property
    def current_state(self) -> AgentState:
        """Get current state."""
        return self._current_state

    def can_transition_to(self, new_state: AgentState) -> Tuple[bool, Optional[str]]:
        """Check if transition is valid."""
        if self._current_state == new_state:
            return True, "Already in this state"

        allowed = VALID_TRANSITIONS.get(self._current_state, [])
        if new_state not in allowed:
            return False, (
                f"Invalid transition: {self._current_state} -> {new_state}. "
                f"Allowed: {allowed}"
            )
        return True, None

    def transition(self, new_state: AgentState, reason: Optional[str] = None) -> None:
        """Transition to new state, raising if invalid."""
        can_transition, error = self.can_transition_to(new_state)
        if not can_transition:
            raise ValueError(error)

        old_state = self._current_state
        self._current_state = new_state
        self._history.append(
            StateTransition(old_state, new_state, datetime.utcnow(), reason)
        )

    def is_terminal(self) -> bool:
        """Check if current state is terminal."""
        return self._current_state in TERMINAL_STATES

    def get_history(self) -> List[Tuple[AgentState, float]]:
        """Get state history as (state, timestamp) tuples."""
        return [(t.to_state, t.timestamp.timestamp()) for t in self._history]

    def reset_to_state(self, state: AgentState, reason: Optional[str] = None) -> None:
        """Reset to a specific state (for testing/rollback)."""
        if state not in AgentState:
            raise ValueError(f"Invalid state: {state}")
        self._current_state = state
        self._history.append(
            StateTransition(None, state, datetime.utcnow(), f"reset: {reason}")
        )

    def __str__(self) -> str:
        return str(self._current_state)

    def __repr__(self) -> str:
        return f"AgentStateMachine(state={self._current_state})"
