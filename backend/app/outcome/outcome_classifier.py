"""
Outcome Classifier — Grades verification outcomes and categorizes task success.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("devpilot.outcome.outcome_classifier")


class OutcomeGrade(str, Enum):
    SUCCESS = "success"
    RECOVERABLE = "recoverable"
    ESCALATE = "escalate"


@dataclass
class OutcomeClassification:
    grade: OutcomeGrade
    evidence_score: float               # 0.0 to 1.0
    risk_score: float                   # 0.0 to 1.0
    reasoning: str


class OutcomeClassifier:
    """Classifies verification results into success grades."""

    def classify_outcome(
        self,
        test_failures: int,
        lint_passed: bool,
        type_checks_passed: bool,
        security_passed: bool,
        contract_violations: list[str]
    ) -> OutcomeClassification:
        """Evaluate evidence parameters to produce a task outcome classification."""
        evidence_score = 1.0
        risk_score = 0.0
        reasoning = "All checks passed successfully."

        # Deduct for test failures
        if test_failures > 0:
            evidence_score -= 0.4
            risk_score += 0.3
            reasoning = f"Failed {test_failures} verification tests."

        # Deduct for contract violations
        if contract_violations:
            evidence_score -= 0.3
            risk_score += 0.4
            reasoning += f" Contract violations found: {contract_violations}"

        # Deduct for security
        if not security_passed:
            evidence_score -= 0.5
            risk_score += 0.6
            reasoning += " Security scan failed."

        # Deduct for lint/type errors
        if not lint_passed or not type_checks_passed:
            evidence_score -= 0.1
            risk_score += 0.1

        # Classify grade
        if evidence_score >= 0.85:
            grade = OutcomeGrade.SUCCESS
        elif evidence_score >= 0.5:
            grade = OutcomeGrade.RECOVERABLE
        else:
            grade = OutcomeGrade.ESCALATE

        logger.info(f"Outcome Classified: Grade={grade.value}, Evidence={evidence_score:.2f}, Risk={risk_score:.2f}")
        return OutcomeClassification(
            grade=grade,
            evidence_score=round(evidence_score, 2),
            risk_score=round(risk_score, 2),
            reasoning=reasoning
        )


# ── Singleton ───────────────────────────────────────────────────────────────

outcome_classifier = OutcomeClassifier()
