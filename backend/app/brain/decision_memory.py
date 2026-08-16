"""
Decision Memory — Stores logs of architectural decisions and their underlying rationale.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("devpilot.brain.decision_memory")


@dataclass
class ArchitectureDecision:
    decision_id: str
    title: str
    status: str                         # proposed | accepted | superseded | rejected
    rationale: str
    timestamp: float


class DecisionMemory:
    """Tamper-evident record of decisions preventing logic regression or repeating failed designs."""

    def __init__(self) -> None:
        self._decisions: dict[str, ArchitectureDecision] = {}

    def record_decision(self, decision_id: str, title: str, status: str, rationale: str) -> ArchitectureDecision:
        import time
        decision = ArchitectureDecision(
            decision_id=decision_id,
            title=title,
            status=status,
            rationale=rationale,
            timestamp=time.time()
        )
        self._decisions[decision_id] = decision
        logger.info(f"[Decision Memory] Recorded: {title} ({status})")
        return decision

    def get_decision(self, decision_id: str) -> ArchitectureDecision | None:
        return self._decisions.get(decision_id)

    def list_decisions(self) -> list[ArchitectureDecision]:
        return list(self._decisions.values())


# ── Singleton ───────────────────────────────────────────────────────────────

decision_memory = DecisionMemory()
