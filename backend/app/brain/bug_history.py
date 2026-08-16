"""
Bug History — Indexes historical bug patterns, stack traces, and applied remediation code.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("devpilot.brain.bug_history")


@dataclass
class BugRecord:
    bug_id: str
    error_message: str
    file_path: str
    line_number: int
    resolution: str
    remediation_pattern: str            # regex/description of fix code
    timestamp: float


class BugHistory:
    """Historical index preventing the same bugs from recurring by sharing past fixes."""

    def __init__(self) -> None:
        self._bugs: dict[str, BugRecord] = {}

    def record_bug(
        self,
        bug_id: str,
        error_message: str,
        file_path: str,
        line_number: int,
        resolution: str,
        remediation_pattern: str,
    ) -> BugRecord:
        import time
        record = BugRecord(
            bug_id=bug_id,
            error_message=error_message,
            file_path=file_path,
            line_number=line_number,
            resolution=resolution,
            remediation_pattern=remediation_pattern,
            timestamp=time.time()
        )
        self._bugs[bug_id] = record
        logger.info(f"[Bug History] Recorded resolution for bug: {bug_id} in {file_path}")
        return record

    def find_remediation(self, error_message: str) -> BugRecord | None:
        """Check if we have an existing fix for a matching error string."""
        err_lower = error_message.lower()
        for record in self._bugs.values():
            if record.error_message.lower() in err_lower or err_lower in record.error_message.lower():
                return record
        return None


# ── Singleton ───────────────────────────────────────────────────────────────

bug_history = BugHistory()
