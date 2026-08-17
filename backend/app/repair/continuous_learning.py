"""
Continuous Learning — Orchestrates long term memory consolidation of bug resolution mappings.
"""
from __future__ import annotations

import logging

from ..brain.bug_history import bug_history

logger = logging.getLogger("loopix.repair.continuous_learning")


class ContinuousLearning:
    """Consolidates short-term session outcomes into long-term system memory."""

    def record_successful_repair(self, failure_msg: str, resolved_code: str, file_path: str) -> None:
        """Register successful fix mapping in bug history database."""
        bug_id = f"bug_learn_{len(bug_history._bugs) + 1}"
        resolution = f"Replaced broken statements with: {resolved_code[:100]}..."
        
        bug_history.record_bug(
            bug_id=bug_id,
            error_message=failure_msg,
            file_path=file_path,
            line_number=1,
            resolution=resolution,
            remediation_pattern=resolved_code
        )
        logger.info(f"Learned repair convention: registered {bug_id} for error '{failure_msg[:40]}'")

    def suggest_repair(self, failure_msg: str) -> str | None:
        """Check bug history for a previously successful resolution pattern."""
        record = bug_history.find_remediation(failure_msg)
        if record:
            logger.info(f"Found matching repair pattern from bug record: {record.bug_id}")
            return record.remediation_pattern
        return None


# ── Singleton ───────────────────────────────────────────────────────────────

continuous_learning = ContinuousLearning()
