"""
Workflow Store — Durable persistence for agent workflow states.

Enables checkpointing and restoring state of complex workflows (e.g. LangGraph paths, custom state machines).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentos.infrastructure.workflow_store")


@dataclass
class WorkflowState:
    """Represents the execution state of a workflow."""
    workflow_id: str
    workflow_type: str
    status: str                         # running | completed | failed | paused
    current_node: str
    state_data: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None


class WorkflowStore:
    """Stores and retrieves workflow states for checkpointing/resuming."""

    def __init__(self) -> None:
        self._states: Dict[str, WorkflowState] = {}

    def save_state(
        self,
        workflow_id: str,
        workflow_type: str,
        status: str,
        current_node: str,
        state_data: Dict[str, Any],
        error: Optional[str] = None,
    ) -> WorkflowState:
        """Create or update a workflow state entry."""
        now = time.time()
        existing = self._states.get(workflow_id)

        if existing:
            existing.status = status
            existing.current_node = current_node
            existing.state_data = state_data
            existing.updated_at = now
            existing.error = error
            state = existing
        else:
            state = WorkflowState(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                status=status,
                current_node=current_node,
                state_data=state_data,
                created_at=now,
                updated_at=now,
                error=error,
            )
            self._states[workflow_id] = state

        logger.debug(f"Workflow state checkpointed: {workflow_id} (node: {current_node}, status: {status})")
        return state

    def get_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Retrieve a workflow state by ID."""
        return self._states.get(workflow_id)

    def list_workflows(self, workflow_type: Optional[str] = None, status: Optional[str] = None) -> List[WorkflowState]:
        """List workflow states filtered by type and status."""
        return [
            w for w in self._states.values()
            if (workflow_type is None or w.workflow_type == workflow_type)
            and (status is None or w.status == status)
        ]

    def delete_state(self, workflow_id: str) -> None:
        self._states.pop(workflow_id, None)

    def clear(self) -> None:
        self._states.clear()


# ── Singleton ───────────────────────────────────────────────────────────────

workflow_store = WorkflowStore()
