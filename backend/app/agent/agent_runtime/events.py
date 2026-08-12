"""
Structured Agent Events — Step 7 canonical event stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import json
from typing import Any, Dict, Optional


@dataclass
class AgentEvent:
    """Canonical structured event consumed by the frontend and loggers.

    Each event represents a single state change or execution milestone in an Agent session.
    """
    session_id: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "type": self.type,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# Pre-defined event types matching Step 7 specification
EVENT_AGENT_STARTED = "agent.started"
EVENT_AGENT_STATE_CHANGED = "agent.state_changed"
EVENT_AGENT_PLAN_CREATED = "agent.plan.created"
EVENT_TOOL_STARTED = "tool.started"
EVENT_TOOL_COMPLETED = "tool.completed"
EVENT_FILE_CHANGED = "file.changed"
EVENT_COMMAND_STARTED = "command.started"
EVENT_COMMAND_OUTPUT = "command.output"
EVENT_COMMAND_COMPLETED = "command.completed"
EVENT_VERIFICATION_STARTED = "verification.started"
EVENT_VERIFICATION_COMPLETED = "verification.completed"
EVENT_AGENT_ERROR = "agent.error"
EVENT_AGENT_CANCELLED = "agent.cancelled"
EVENT_AGENT_COMPLETED = "agent.completed"

# Phase 3 Autonomous & Self-Repair Events
EVENT_AGENT_CONTRACT_CREATED = "agent.contract.created"
EVENT_PLAN_STEP_STARTED = "agent.plan.step_started"
EVENT_PLAN_STEP_COMPLETED = "agent.plan.step_completed"
EVENT_REPAIR_STARTED = "agent.repair.started"
EVENT_REPAIR_FAILED = "agent.repair.failed"
EVENT_REPAIR_LOOP_DETECTED = "agent.repair.loop_detected"
EVENT_REVIEW_COMPLETED = "agent.review.completed"
EVENT_APPROVAL_REQUIRED = "agent.approval_required"
EVENT_CHECKPOINT_CREATED = "agent.checkpoint.created"
