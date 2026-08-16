import hashlib
import json
from collections import Counter, deque
from typing import Any

from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.runtime.agent_runtime import (
    ActionEvent,
    Event,
    ObservationEvent,
)


class AgentMonitor:
    """
    Per-agent monitor that runs inside BaseParallelAgent.run() for every event.
    Implements advanced stuck/loop detection patterns, cost ceilings, and iteration watchdogs.
    """

    def __init__(self, subtask_id: str, config: SystemConfig):
        import time
        self.subtask_id = subtask_id
        self.config = config
        self.cost = 0.0
        self.iterations = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.start_time = time.time()

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
            self.cost += event.cost_usd or 0.0
        if hasattr(event, "input_tokens"):
            self.input_tokens += getattr(event, "input_tokens", 0) or 0
        if hasattr(event, "output_tokens"):
            self.output_tokens += getattr(event, "output_tokens", 0) or 0

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
        import time
        elapsed = time.time() - self.start_time
        max_timeout = getattr(self.config, "max_agent_execution_timeout_seconds", 300.0)
        if elapsed >= max_timeout:
            return True
        if self.cost >= self.config.max_agent_cost_usd:
            return True
        if self.iterations >= self.config.max_iterations_per_agent:
            return True
        max_tok = getattr(self.config, "max_agent_tokens", 1000000)
        if (self.input_tokens + self.output_tokens) >= max_tok:
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


import re
from collections import defaultdict


def normalize_error_signature(error_msg: str) -> str:
    """Normalize error message by stripping line numbers, timestamps, memory addresses, paths, and GUIDs.

    Two errors differing only by line numbers or timestamps will produce identical normalized signatures.
    """
    if not error_msg or not isinstance(error_msg, str):
        return ""

    text = error_msg.strip()

    # 1. Remove ISO timestamps (e.g., 2026-07-27T18:04:13) and clock times
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?", "<TIMESTAMP>", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<TIME>", text)

    # 2. Remove memory addresses (e.g., 0x7fa8b9c10)
    text = re.sub(r"0x[0-9a-fA-F]+\b", "<HEX_ADDR>", text)

    # 3. Remove GUIDs / UUIDs
    text = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<UUID>", text)

    # 4. Remove line and column numbers (e.g., line 42, :123:45, :89)
    text = re.sub(r"\bline\s+\d+\b", "line <N>", text, flags=re.IGNORECASE)
    text = re.sub(r":\d+:\d+", ":<LINE>:<COL>", text)
    text = re.sub(r":\d+\b", ":<LINE>", text)

    # 5. Remove absolute file paths (e.g. C:\Users\... or /home/...)
    text = re.sub(r"(?:[a-zA-Z]:)?[/\\][\w.\-_/\\]+\.(?:py|js|ts|tsx|jsx|json|md|c|cpp|h|go|rs)", "<FILE_PATH>", text)

    # 6. Normalize whitespace runs
    text = re.sub(r"\s+", " ", text).strip()
    return text


class StuckDetector:
    """Evaluates subtasks and execution results to detect stuck, stalled, or looping agents.

    Also tracks recurring error signatures per subtask to trigger web search fallback
    after threshold repeats AND debugging agent attempts.
    """

    def __init__(self, config: SystemConfig | None = None):
        self.config = config or SystemConfig()
        # subtask_id -> list of normalized error signatures
        self._error_signatures: dict[str, list[str]] = defaultdict(list)
        # subtask_id -> bool indicating if Debugging Agent attempt was made
        self._debugging_attempted: dict[str, bool] = defaultdict(bool)

    def record_debugging_attempt(self, subtask_id: str) -> None:
        """Record that the Debugging Agent has attempted to fix this subtask."""
        self._debugging_attempted[subtask_id] = True

    def check(
        self,
        subtasks: list[Any],
        results: list[Any],
        repeat_error_threshold: int = 2,
    ) -> list[str]:
        """Checks subtasks and results for stuck states. Returns list of stuck subtask IDs."""
        detailed = self.check_detailed(subtasks, results, repeat_error_threshold)
        return detailed["stuck_ids"]

    def check_detailed(
        self,
        subtasks: list[Any],
        results: list[Any],
        repeat_error_threshold: int = 2,
    ) -> dict[str, Any]:
        """Detailed stuck check returning stuck_ids, web_search_task_ids, and active error_signatures."""
        stuck_ids = []
        web_search_task_ids = []
        error_map = {}

        for r in results:
            status = getattr(r, "status", "")
            subtask_id = getattr(r, "subtask_id", None)
            if not subtask_id:
                continue

            output = getattr(r, "output", "") or ""

            # Check if execution returned an error or stuck status
            is_error = status in ("error", "stuck", "failed") or any(
                kw in output.lower() for kw in ("error", "failed", "exception", "stuck", "loop detected")
            )

            if is_error and output:
                sig = normalize_error_signature(output)
                if sig:
                    self._error_signatures[subtask_id].append(sig)
                    error_map[subtask_id] = sig

                    # Count how many times this specific normalized error signature has occurred
                    sig_count = self._error_signatures[subtask_id].count(sig)

                    # Trigger web search ONLY if:
                    # 1. Same normalized error fired >= repeat_error_threshold times
                    # 2. Debugging Agent has ALREADY attempted to fix it first
                    if sig_count >= repeat_error_threshold and self._debugging_attempted.get(subtask_id, False):
                        if subtask_id not in web_search_task_ids:
                            web_search_task_ids.append(subtask_id)

            if status == "stuck" or any(kw in output.lower() for kw in ("stuck", "stuckerror", "loop detected")):
                if subtask_id not in stuck_ids:
                    stuck_ids.append(subtask_id)

        return {
            "stuck_ids": stuck_ids,
            "web_search_task_ids": web_search_task_ids,
            "error_signatures": error_map,
        }


