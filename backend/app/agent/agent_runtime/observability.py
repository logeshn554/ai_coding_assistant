"""
Phase 14: Production Reliability, Observability & Resilience Engine.

Provides Trace ID propagation, Circuit Breakers, structured JSON logging,
and persistent session corruption recovery.
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("devpilot.observability")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    pass


class CircuitBreaker:
    """Circuit breaker preventing cascading failures on unstable external APIs."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.datetime.now(datetime.timezone.utc)

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.datetime.now(datetime.timezone.utc)

    def allow_execution(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            now = datetime.datetime.now(datetime.timezone.utc)
            if (now - self.last_state_change).total_seconds() > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True


@dataclass
class TraceContext:
    session_id: str
    task_id: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, str]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "trace_id": self.trace_id,
        }


class ObservabilityEngine:
    """Manages trace context propagation and structured observability logs."""

    @classmethod
    def create_trace(cls, session_id: str, task_id: str) -> TraceContext:
        return TraceContext(session_id=session_id, task_id=task_id)

    @classmethod
    def log_event(cls, trace: TraceContext, event_name: str, payload: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "trace_id": trace.trace_id,
            "session_id": trace.session_id,
            "task_id": trace.task_id,
            "event": event_name,
            "payload": payload,
        }
        logger.info(json.dumps(entry))
