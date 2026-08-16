"""
Execution Planner & Step Checkpoint Manager — Step 3, 4, 5 requirements.

Constructs executable multi-step plans with explicit statuses (PENDING, RUNNING,
COMPLETED, FAILED, SKIPPED, BLOCKED) and step-level checkpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .task_contract import AgentTaskContract


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


@dataclass
class PlanStep:
    """Individual executable step within an ExecutionPlan."""
    id: str
    description: str
    step_type: str  # investigate | implementation | testing | verification
    dependencies: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    expected_changes: list[str] = field(default_factory=list)
    verification: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "step_type": self.step_type,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "expected_changes": self.expected_changes,
            "verification": self.verification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            step_type=data.get("step_type", "implementation"),
            dependencies=data.get("dependencies", []),
            status=StepStatus(data.get("status", "PENDING")),
            expected_changes=data.get("expected_changes", []),
            verification=data.get("verification", ""),
        )


@dataclass
class ExecutionPlan:
    """Canonical multi-step plan executed by AgentRuntime."""
    contract_goal: str
    steps: list[PlanStep] = field(default_factory=list)
    current_step_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_goal": self.contract_goal,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_id": self.current_step_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        return cls(
            contract_goal=data.get("contract_goal", ""),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
            current_step_id=data.get("current_step_id"),
        )

    def mark_step_status(self, step_id: str, status: StepStatus) -> None:
        for s in self.steps:
            if s.id == step_id:
                s.status = status
                break

    def get_next_step(self) -> PlanStep | None:
        for s in self.steps:
            if s.status == StepStatus.PENDING:
                return s
        return None


class ExecutionPlanner:
    """Generates executable plans from an AgentTaskContract."""

    @classmethod
    def generate_plan(cls, contract: AgentTaskContract) -> ExecutionPlan:
        steps = [
            PlanStep(
                id="investigate-context",
                description="Investigate codebase and retrieve relevant symbols/files",
                step_type="investigate",
                dependencies=[],
                verification="context_engine_ready",
            ),
            PlanStep(
                id="implement-changes",
                description=f"Implement changes for: '{contract.goal}'",
                step_type="implementation",
                dependencies=["investigate-context"],
                expected_changes=contract.scope,
                verification="file_written",
            ),
            PlanStep(
                id="verify-implementation",
                description="Execute targeted tests and verification checks",
                step_type="verification",
                dependencies=["implement-changes"],
                verification="test_pass",
            ),
        ]
        return ExecutionPlan(contract_goal=contract.goal, steps=steps)
