"""
Policy Engine & Command Safety Classifier — Step 20, 21, 22 requirements.

Classifies command safety risk (LOW, MEDIUM, HIGH) and enforces mode policies
(Assisted, Autonomous, Strict) with approval integration.
"""

from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    ASSISTED = "Assisted"
    AUTONOMOUS = "Autonomous"
    STRICT = "Strict"


class CommandRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyEngine:
    """Classifies command risks and enforces execution mode approval policies."""

    @classmethod
    def classify_command_risk(cls, command: str) -> CommandRiskLevel:
        cmd_lower = command.lower().strip()

        # HIGH risk patterns
        if any(kw in cmd_lower for kw in ["rm ", "git reset", "git clean", "drop database", "migration", "git push"]):
            return CommandRiskLevel.HIGH

        # MEDIUM risk patterns
        if any(kw in cmd_lower for kw in ["npm install", "pip install", "pnpm add", "yarn add"]):
            return CommandRiskLevel.MEDIUM

        # LOW risk patterns (tests, reads, status)
        return CommandRiskLevel.LOW

    @classmethod
    def is_approval_required(cls, mode: ExecutionMode, risk: CommandRiskLevel) -> bool:
        if mode == ExecutionMode.STRICT:
            return risk in (CommandRiskLevel.MEDIUM, CommandRiskLevel.HIGH)
        elif mode == ExecutionMode.ASSISTED:
            return risk == CommandRiskLevel.HIGH
        elif mode == ExecutionMode.AUTONOMOUS:
            return risk == CommandRiskLevel.HIGH  # High risk operations always require approval
        return False
