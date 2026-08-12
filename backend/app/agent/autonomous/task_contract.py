"""
Task Contract Engine — Step 2 requirement.

Converts an incoming user coding prompt into a strongly typed AgentTaskContract
defining goals, scope boundaries, constraints, acceptance criteria, verification rules,
risk level, and repair budgets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional


@dataclass
class AgentTaskContract:
    """Structured contract for autonomous coding execution."""
    goal: str
    scope: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW | MEDIUM | HIGH
    max_steps: int = 15
    max_repair_rounds: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "scope": self.scope,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "verification_requirements": self.verification_requirements,
            "risk_level": self.risk_level,
            "max_steps": self.max_steps,
            "max_repair_rounds": self.max_repair_rounds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTaskContract":
        return cls(
            goal=data.get("goal", ""),
            scope=data.get("scope", []),
            constraints=data.get("constraints", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            verification_requirements=data.get("verification_requirements", []),
            risk_level=data.get("risk_level", "LOW"),
            max_steps=data.get("max_steps", 15),
            max_repair_rounds=data.get("max_repair_rounds", 5),
        )


class TaskContractGenerator:
    """Generates structured task contracts from prompt analysis."""

    @classmethod
    def create_contract(cls, task_description: str, workspace_root: Optional[str] = None) -> AgentTaskContract:
        desc = task_description.strip()
        risk = "LOW"

        # Risk classification
        if any(kw in desc.lower() for kw in ["delete", "remove", "drop", "schema", "db", "migration", "reset"]):
            risk = "HIGH"
        elif any(kw in desc.lower() for kw in ["auth", "login", "password", "security", "token", "payment"]):
            risk = "MEDIUM"

        # Scope extraction
        words = re.findall(r"\b[A-Za-z0-9_]{3,}\b", desc)
        scope = list(set([w for w in words if w.lower() not in {"fix", "add", "the", "and", "for", "with", "from", "bug", "issue"}]))

        # Criteria generation
        criteria = [
            f"Implementation completes: '{desc}'",
            "No syntax or type errors introduced",
            "Targeted tests pass successfully",
        ]

        verification = ["syntax_check", "type_check", "unit_test"]

        return AgentTaskContract(
            goal=desc,
            scope=scope[:5],
            constraints=["Do not modify unrelated codebase files", "Respect security filtering rules"],
            acceptance_criteria=criteria,
            verification_requirements=verification,
            risk_level=risk,
            max_steps=15,
            max_repair_rounds=5,
        )
