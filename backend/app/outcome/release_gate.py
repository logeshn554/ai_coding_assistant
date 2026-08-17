"""
Release Gate — Decides whether to auto release changes or request explicit human confirmation.
"""
from __future__ import annotations

import logging

from .outcome_classifier import OutcomeClassification, OutcomeGrade

logger = logging.getLogger("loopix.outcome.release_gate")


class ReleaseGate:
    """Gates codebase modifications prior to git commits."""

    def should_auto_release(self, classification: OutcomeClassification) -> bool:
        """Evaluate outcome to determine if human gatekeeper approval is needed.

        Only auto-releases if classification is SUCCESS and risk score is low.
        """
        if classification.grade != OutcomeGrade.SUCCESS:
            logger.info("Release Gate: Blocked auto-release (grade is not SUCCESS).")
            return False

        if classification.risk_score >= 0.4:
            logger.info("Release Gate: Human approval required (risk score too high).")
            return False

        logger.info("Release Gate: Approved for auto-release.")
        return True


# ── Singleton ───────────────────────────────────────────────────────────────

release_gate = ReleaseGate()
