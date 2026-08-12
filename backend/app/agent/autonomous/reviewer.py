"""
Agent Reviewer & Acceptance Criteria Evaluator — Step 16, 17, 18 requirements.

Evaluates post-verification changes against task contract acceptance criteria,
distinguishing technical verification (passing tests) from requirement satisfaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .task_contract import AgentTaskContract
from .verification_engine import VerificationResult


@dataclass
class ReviewFinding:
    criterion: str
    satisfied: bool
    reason: str


@dataclass
class ReviewResult:
    approved: bool
    findings: List[ReviewFinding] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "findings": [
                {
                    "criterion": f.criterion,
                    "satisfied": f.satisfied,
                    "reason": f.reason,
                }
                for f in self.findings
            ],
            "confidence": self.confidence,
        }


class AgentReviewer:
    """Evaluates task completion against acceptance criteria."""

    @classmethod
    def review_task(
        cls,
        contract: AgentTaskContract,
        changed_files: List[str],
        verification_res: VerificationResult,
    ) -> ReviewResult:
        findings: List[ReviewFinding] = []
        all_satisfied = True

        for criterion in contract.acceptance_criteria:
            if "syntax" in criterion.lower() or "type" in criterion.lower():
                sat = verification_res.success
                reason = "Verification checks passed" if sat else "Verification checks failed"
            elif "test" in criterion.lower():
                sat = verification_res.success
                reason = "Tests executed and passed" if sat else "Tests failed"
            else:
                # General requirement completion check
                sat = len(changed_files) > 0 and verification_res.success
                reason = f"Changed {len(changed_files)} files with passing verification" if sat else "No files modified or verification failed"

            findings.append(ReviewFinding(criterion=criterion, satisfied=sat, reason=reason))
            if not sat:
                all_satisfied = False

        confidence = 0.95 if all_satisfied else 0.40
        return ReviewResult(
            approved=all_satisfied,
            findings=findings,
            confidence=confidence,
        )
