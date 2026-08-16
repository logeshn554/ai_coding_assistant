"""
Stuck & Repeated Error Detector — Detects loop patterns and repeated error states.

Checks if agents are calling the same tool with the same arguments, 
encountering the same error signature repeatedly, or trapped in alternating ping-pong states.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger("agent_runtime.orchestration.stuck_detector")


def normalize_error_signature(error_msg: str) -> str:
    """Normalize error messages to identify repeated root-cause bugs.

    Strips out line numbers, memory addresses, timestamps, file paths, and GUIDs
    so that two exceptions differing only by context produce the same signature.
    """
    if not error_msg or not isinstance(error_msg, str):
        return ""

    text = error_msg.strip()

    # 1. Remove ISO timestamps and time patterns
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?", "<TIMESTAMP>", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<TIME>", text)

    # 2. Remove memory addresses
    text = re.sub(r"0x[0-9a-fA-F]+\b", "<HEX_ADDR>", text)

    # 3. Remove GUIDs / UUIDs
    text = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<UUID>", text)

    # 4. Remove line numbers
    text = re.sub(r"\bline\s+\d+\b", "line <N>", text, flags=re.IGNORECASE)
    text = re.sub(r":\d+:\d+", ":<LINE>:<COL>", text)
    text = re.sub(r":\d+\b", ":<LINE>", text)

    # 5. Remove absolute paths
    text = re.sub(r"(?:[a-zA-Z]:)?[/\\][\w.\-_/\\]+\.(?:py|js|ts|tsx|jsx|json|md)", "<FILE_PATH>", text)

    # 6. Collapse whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


class StuckDetector:
    """Evaluates agent execution history and logs to find stuck execution or error loops.

    Checks:
    - Same tool called repeatedly with the same parameters.
    - Repeated identical normalized error logs.
    - Ping-pong alternating patterns (e.g. read A, edit A, read A, edit A).
    """

    def __init__(self, repeat_threshold: int = 3) -> None:
        self.repeat_threshold = repeat_threshold
        # task_id -> list of normalized error signatures
        self._task_errors: dict[str, list[str]] = defaultdict(list)
        # task_id -> history of tool calls: list of (tool_name, tool_args_hash)
        self._tool_history: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def record_tool_call(self, task_id: str, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """Record a tool call and check if it represents a repeated loop.

        Returns:
            True if a stuck loop is detected, False otherwise.
        """
        # Create a stable hash of the tool arguments
        import json
        try:
            args_str = json.dumps(tool_args, sort_keys=True)
        except Exception:
            args_str = str(tool_args)
        args_hash = hashlib.sha256(args_str.encode()).hexdigest()[:16]

        history = self._tool_history[task_id]
        history.append((tool_name, args_hash))

        # Keep history window capped
        if len(history) > 20:
            history.pop(0)

        # Check 1: Same tool + arguments called repeatedly
        recent_calls = history[-self.repeat_threshold:]
        if len(recent_calls) >= self.repeat_threshold:
            if len(set(recent_calls)) == 1:
                logger.warning(f"Task '{task_id}' stuck: Tool '{tool_name}' called {self.repeat_threshold} times with identical args.")
                return True

        # Check 2: Alternating ping-pong loop (A -> B -> A -> B -> A -> B)
        if len(history) >= 6:
            last_6 = history[-6:]
            if last_6[0] == last_6[2] == last_6[4] and last_6[1] == last_6[3] == last_6[5]:
                logger.warning(f"Task '{task_id}' stuck: Alternating tool call loop detected: {last_6}")
                return True

        return False

    def record_error(self, task_id: str, error_message: str) -> bool:
        """Record an error signature and check if it has repeated past the threshold.

        Returns:
            True if the error is repeatedly firing without modification, False otherwise.
        """
        sig = normalize_error_signature(error_message)
        if not sig:
            return False

        self._task_errors[task_id].append(sig)
        count = self._task_errors[task_id].count(sig)

        if count >= self.repeat_threshold:
            logger.warning(f"Task '{task_id}' stuck: Error signature '{sig}' has repeated {count} times.")
            return True

        return False

    def clear(self, task_id: str) -> None:
        """Reset historical loop counters for a task (e.g. after a repair or model switch)."""
        self._task_errors.pop(task_id, None)
        self._tool_history.pop(task_id, None)
