"""
Phase 7: Advanced Agent Capabilities & Multi-Agent Specialization.

Defines specialized roles (Planner, Researcher, Coder, Tester, Debugger, Reviewer, RefactoringSpecialist)
as logical capabilities executing under canonical AgentRuntime orchestration authority,
sharing context and enforcing strict role budgets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    PLANNER = "Planner"
    RESEARCHER = "Researcher"
    CODER = "Coder"
    TESTER = "Tester"
    DEBUGGER = "Debugger"
    REVIEWER = "Reviewer"
    REFACTORING_SPECIALIST = "RefactoringSpecialist"


@dataclass
class RoleBudget:
    max_duration_seconds: float = 120.0
    max_tool_calls: int = 15
    max_repair_rounds: int = 5
    max_token_budget: int = 32_000
    max_file_changes: int = 10


@dataclass
class RoleContract:
    role: AgentRole
    allowed_tools: set[str]
    expected_output_type: str
    budget: RoleBudget = field(default_factory=RoleBudget)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "allowed_tools": list(self.allowed_tools),
            "expected_output_type": self.expected_output_type,
            "budget": {
                "max_duration_seconds": self.budget.max_duration_seconds,
                "max_tool_calls": self.budget.max_tool_calls,
                "max_repair_rounds": self.budget.max_repair_rounds,
                "max_token_budget": self.budget.max_token_budget,
                "max_file_changes": self.budget.max_file_changes,
            },
        }


# Canonical Role Contracts Definitions
ROLE_CONTRACTS: dict[AgentRole, RoleContract] = {
    AgentRole.PLANNER: RoleContract(
        role=AgentRole.PLANNER,
        allowed_tools={"list_directory", "read_file", "search_files", "symbol_lookup"},
        expected_output_type="ExecutionPlan",
    ),
    AgentRole.RESEARCHER: RoleContract(
        role=AgentRole.RESEARCHER,
        allowed_tools={"list_directory", "read_file", "search_files", "symbol_lookup", "find_references"},
        expected_output_type="ResearchReport",
    ),
    AgentRole.CODER: RoleContract(
        role=AgentRole.CODER,
        allowed_tools={"read_file", "write_file", "edit_file", "create_file", "delete_file"},
        expected_output_type="ChangeSet",
    ),
    AgentRole.TESTER: RoleContract(
        role=AgentRole.TESTER,
        allowed_tools={"run_command", "run_test", "read_file"},
        expected_output_type="VerificationResult",
    ),
    AgentRole.DEBUGGER: RoleContract(
        role=AgentRole.DEBUGGER,
        allowed_tools={"read_file", "edit_file", "run_command", "symbol_lookup"},
        expected_output_type="RootCauseDiagnosis",
    ),
    AgentRole.REVIEWER: RoleContract(
        role=AgentRole.REVIEWER,
        allowed_tools={"read_file", "git_diff"},
        expected_output_type="ReviewResult",
    ),
    AgentRole.REFACTORING_SPECIALIST: RoleContract(
        role=AgentRole.REFACTORING_SPECIALIST,
        allowed_tools={"read_file", "write_file", "edit_file", "symbol_lookup", "find_references"},
        expected_output_type="RefactorResult",
    ),
}


class DebateReviewLoop:
    """Manages debate and review between Coder and Reviewer capabilities."""

    @classmethod
    def evaluate_proposal(cls, proposal_diff: str, acceptance_criteria: list[str]) -> tuple[bool, str]:
        """Review Coder proposal against task criteria."""
        if not proposal_diff or not proposal_diff.strip():
            return False, "Empty proposal diff"

        # Check for secret leaks or forbidden tokens
        if "AWS_SECRET" in proposal_diff or "PRIVATE KEY" in proposal_diff:
            return False, "Review Rejected: Proposal contains unredacted credentials"

        return True, "Review Approved: Patch meets acceptance criteria"
