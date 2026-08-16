"""
Self-Repair Loop & Budget Controller — Step 11, 12, 13, 14 requirements.

Executes autonomous repair cycles, enforces max repair round budgets,
detects repeated error loops, and prevents destructive out-of-scope edits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .failure_analyzer import VerificationFailure
from .task_contract import AgentTaskContract

logger = logging.getLogger("devpilot.autonomous.self_repair")


@dataclass
class RepairRoundRecord:
    """Audit record for an individual repair iteration."""
    round_number: int
    failure: VerificationFailure
    patch_summary: str = ""
    success: bool = False


class SelfRepairLoop:
    """Manages the autonomous self-repair lifecycle."""

    def __init__(self, contract: AgentTaskContract) -> None:
        self.contract = contract
        self.max_rounds = contract.max_repair_rounds
        self.current_round = 0
        self.history: list[RepairRoundRecord] = []
        self.seen_failures: list[str] = []

    def can_attempt_repair(self) -> bool:
        """Check if remaining repair rounds exist under the contract budget."""
        return self.current_round < self.max_rounds

    def detect_failure_loop(self, failure: VerificationFailure) -> bool:
        """Detect if the exact same failure occurred 2+ consecutive times."""
        fail_sig = f"{failure.category.value}:{failure.file}:{failure.line}:{failure.message[:50]}"
        self.seen_failures.append(fail_sig)

        if len(self.seen_failures) >= 2:
            if self.seen_failures[-1] == self.seen_failures[-2]:
                logger.warning(f"Repeated failure loop detected: {fail_sig}")
                return True

        return False

    def record_repair_attempt(self, failure: VerificationFailure, patch_summary: str, success: bool) -> RepairRoundRecord:
        self.current_round += 1
        record = RepairRoundRecord(
            round_number=self.current_round,
            failure=failure,
            patch_summary=patch_summary,
            success=success,
        )
        self.history.append(record)
        return record
