"""Phase 4 — Task Memory.

Persistent in-memory execution state per agent session.
Enables reliable 'continue' and 'resume' behavior.

State tracked:
  goal            — original user request
  steps           — ordered task steps with status
  files_read      — files the agent has read this session
  files_written   — files the agent has created/modified
  errors          — list of errors encountered
  retry_counts    — per-step retry count
  current_step    — index of the step currently in progress
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("devpilot.agent.task_memory")


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    """A single step in the agent's plan."""
    id: int
    task: str                          # Human-readable description
    step_type: str = "general"         # "context", "create", "implement", "test", "validate"
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""                   # Output of the step
    error: str = ""                    # Error if failed
    retry_count: int = 0
    deps: list[int] = field(default_factory=list)  # IDs of prerequisite steps
    started_at: float = 0.0
    completed_at: float = 0.0

    def is_ready(self, completed_ids: set[int]) -> bool:
        """Return True if all dependencies are completed."""
        return all(dep in completed_ids for dep in self.deps)

    def mark_started(self):
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = time.monotonic()

    def mark_completed(self, result: str = ""):
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = time.monotonic()

    def mark_failed(self, error: str = ""):
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = time.monotonic()


@dataclass
class TaskMemory:
    """Full execution state for one agent run.

    Attach one TaskMemory instance per AgentSession. When the user sends
    'continue', call resume() to get the next pending step.
    """
    goal: str = ""
    intent: str = ""                   # IntentType string
    steps: list[TaskStep] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    file_edits: dict[str, dict[str, int]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    last_updated: float = field(default_factory=time.monotonic)
    is_complete: bool = False
    completion_reason: str = ""        # "validated", "critic_approved", "user_stopped"

    # ── Step management ──────────────────────────────────────────────────

    def add_step(
        self,
        task: str,
        step_type: str = "general",
        deps: list[int] | None = None,
    ) -> TaskStep:
        """Add a new step and return it."""
        step = TaskStep(
            id=len(self.steps) + 1,
            task=task,
            step_type=step_type,
            deps=deps or [],
        )
        self.steps.append(step)
        self._touch()
        return step

    def set_steps(self, steps: list[dict]) -> None:
        """Bulk-set steps from a planning engine output."""
        self.steps = []
        for s in steps:
            self.steps.append(TaskStep(
                id=s.get("id", len(self.steps) + 1),
                task=s.get("task", ""),
                step_type=s.get("type", "general"),
                deps=s.get("deps", []),
            ))
        self._touch()

    def next_pending(self) -> TaskStep | None:
        """Return the next step that is pending and whose deps are done."""
        completed_ids = {s.id for s in self.steps if s.status == TaskStatus.COMPLETED}
        for step in self.steps:
            if step.status == TaskStatus.PENDING and step.is_ready(completed_ids):
                return step
        return None

    def all_completed(self) -> bool:
        return all(s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for s in self.steps)

    def has_failures(self) -> bool:
        return any(s.status == TaskStatus.FAILED for s in self.steps)

    def pending_count(self) -> int:
        return sum(1 for s in self.steps if s.status == TaskStatus.PENDING)

    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == TaskStatus.COMPLETED)

    # ── File tracking ────────────────────────────────────────────────────

    def record_read(self, path: str) -> None:
        if path not in self.files_read:
            self.files_read.append(path)
        self._touch()

    def record_write(self, path: str) -> None:
        if path not in self.files_written:
            self.files_written.append(path)
        self._touch()

    def record_error(self, error: str) -> None:
        self.errors.append(error)
        self._touch()

    # ── Serialisation (for DB persistence / resume) ──────────────────────

    def to_summary_prompt(self) -> str:
        """Format task memory as a prompt section for the LLM."""
        lines = [
            f"**Goal:** {self.goal}",
            f"**Intent:** {self.intent}",
            f"**Progress:** {self.completed_count()}/{len(self.steps)} steps completed",
        ]

        if self.steps:
            lines.append("\n**Steps:**")
            for s in self.steps:
                icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(s.status.value, "•")
                lines.append(f"  {icon} Step {s.id}: {s.task}")
                if s.error:
                    lines.append(f"     Error: {s.error}")

        if self.files_written:
            lines.append(f"\n**Files written:** {', '.join(self.files_written)}")

        if self.errors:
            lines.append(f"\n**Errors encountered:** {len(self.errors)}")
            for e in self.errors[-3:]:  # Show last 3 only
                lines.append(f"  - {e}")

        next_step = self.next_pending()
        if next_step:
            lines.append(f"\n**Next step:** {next_step.task}")

        return "\n".join(lines)

    def reset(self, goal: str = "", intent: str = "") -> None:
        """Reset for a new task."""
        self.goal = goal
        self.intent = intent
        self.steps = []
        self.files_read = []
        self.files_written = []
        self.file_edits = {}
        self.errors = []
        self.is_complete = False
        self.completion_reason = ""
        self.created_at = time.monotonic()
        self._touch()

    def _touch(self):
        self.last_updated = time.monotonic()

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "intent": self.intent,
            "steps": [
                {
                    "id": s.id,
                    "task": s.task,
                    "type": s.step_type,
                    "status": s.status.value,
                    "result": s.result[:500] if s.result else "",
                    "error": s.error,
                    "retry_count": s.retry_count,
                    "deps": s.deps,
                }
                for s in self.steps
            ],
            "files_read": self.files_read,
            "files_written": self.files_written,
            "file_edits": self.file_edits,
            "errors": self.errors[-10:],
            "is_complete": self.is_complete,
            "completion_reason": self.completion_reason,
            "pending_steps": self.pending_count(),
            "completed_steps": self.completed_count(),
        }

    def export_replay_log(self) -> dict[str, Any]:
        """Export full execution log payload for task replay and auditing."""
        return {
            "goal": self.goal,
            "intent": self.intent,
            "is_complete": self.is_complete,
            "completion_reason": self.completion_reason,
            "steps": [
                {
                    "id": s.id,
                    "task": s.task,
                    "step_type": s.step_type,
                    "status": s.status.value,
                    "result": s.result,
                    "error": s.error,
                    "retry_count": s.retry_count,
                    "deps": s.deps,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                }
                for s in self.steps
            ],
            "files_read": self.files_read,
            "files_written": self.files_written,
            "errors": self.errors,
        }
