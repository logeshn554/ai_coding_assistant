import hashlib
import json
from collections import deque, Counter
from typing import Any

from parallel_agent_system.runtime.agent_runtime import Event, ActionEvent, ObservationEvent
from parallel_agent_system.core.config import SystemConfig


class AgentMonitor:
    """
    Per-agent monitor that runs inside BaseParallelAgent.run() for every event.
    Implements advanced stuck/loop detection patterns, cost ceilings, and iteration watchdogs.
    """

    def __init__(self, subtask_id: str, config: SystemConfig):
        self.subtask_id = subtask_id
        self.config = config
        self.cost = 0.0
        self.iterations = 0

        # Monologue tracker
        self._monologue_streak = 0

        # Loop and pattern detection records
        self._pair_counts = Counter()
        self._error_counts = Counter()
        self._ping_pong_counts = Counter()
        self._context_overflow_detected = False

        # Keep a history window of recent event hashes
        self._window: deque[str] = deque(maxlen=20)
        self._last_action_event: ActionEvent | None = None
        self._last_action_hash: str | None = None

    def observe(self, event: Event) -> None:
        """Processes a single event, updating iteration counts, costs, and loop signatures."""
        self.iterations += 1
        
        # Accumulate costs if present on event
        if hasattr(event, "cost_usd"):
            self.cost += event.cost_usd

        # Generate event hash
        h = self._hash(event)
        self._window.append(h)

        if isinstance(event, ActionEvent):
            # Monologue checks (consecutive non-tool actions)
            action = event.action
            is_tool = getattr(action, "is_tool_call", True)
            self._monologue_streak = (self._monologue_streak + 1) if not is_tool else 0

            self._last_action_event = event
            self._last_action_hash = h

        elif isinstance(event, ObservationEvent):
            observation = event.observation
            obs_content = getattr(observation, "content", "")

            # Check Context Window Overflow exceptions
            if "LLMContextWindowExceedError" in obs_content or "context window" in obs_content.lower():
                self._context_overflow_detected = True

            # Pair and error loop checks
            if self._last_action_event and self._last_action_hash:
                action_content = getattr(self._last_action_event.action, "content", "")
                action_type = getattr(self._last_action_event.action, "type", "bash")

                # Combine action and observation content for pair hashing
                pair_key = hashlib.sha256(
                    f"{action_type}:{action_content}:{obs_content}".encode()
                ).hexdigest()[:16]
                self._pair_counts[pair_key] += 1

                # Check error specific loop checks
                is_error = "error" in obs_content.lower() or "failed" in obs_content.lower()
                if is_error:
                    self._error_counts[pair_key] += 1

                # Ping-pong checks (alternating identical states)
                if len(self._window) >= 4:
                    # Alternating action/observation check (A, B, A, B pattern)
                    if self._window[-1] == self._window[-3] and self._window[-2] == self._window[-4]:
                        self._ping_pong_counts[pair_key] += 1

    def is_stuck(self) -> bool:
        """Determines if the agent execution state matches any stuck pattern criteria."""
        # 1. Monologue streak limit hit
        if self._monologue_streak >= self.config.monologue_threshold:
            return True

        # 2. Identical action-observation pairs repeated
        if self._pair_counts and self._pair_counts.most_common(1)[0][1] >= self.config.repeat_pair_threshold:
            return True

        # 3. Repeated error patterns hit
        if self._error_counts and self._error_counts.most_common(1)[0][1] >= 3:
            return True

        # 4. Alternating ping-pong cycles exceeded
        if self._ping_pong_counts and self._ping_pong_counts.most_common(1)[0][1] >= self.config.ping_pong_threshold:
            return True

        # 5. Repeated LLM context window exceeded errors
        if self._context_overflow_detected:
            return True

        return False

    def over_budget(self) -> bool:
        """Checks if the agent has run out of resources or iterations."""
        if self.cost >= self.config.max_agent_cost_usd:
            return True
        if self.iterations >= self.config.max_iterations_per_agent:
            return True
        return False

    @staticmethod
    def _hash(event: Event) -> str:
        """Computes a unique SHA-256 hash representation of an event structure."""
        try:
            dump = event.model_dump()
        except AttributeError:
            dump = str(event)
        
        return hashlib.sha256(
            json.dumps(dump, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]


class StuckDetector:
    """
    Evaluates subtasks and execution results to detect stuck, stalled, or looping agents.
    """

    def __init__(self, config: SystemConfig | None = None):
        self.config = config or SystemConfig()

    def check(self, subtasks: list[Any], results: list[Any]) -> list[str]:
        """
        Checks subtasks and results for stuck states.
        Returns a list of stuck subtask IDs.
        """
        stuck_ids = []
        for r in results:
            status = getattr(r, "status", "")
            subtask_id = getattr(r, "subtask_id", None)
            if not subtask_id:
                continue
            if status == "stuck":
                stuck_ids.append(subtask_id)
            else:
                output = getattr(r, "output", "") or ""
                if any(kw in output.lower() for kw in ("stuck", "stuckerror", "loop detected")):
                    stuck_ids.append(subtask_id)
        return stuck_ids

