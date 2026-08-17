"""
Root Cause Analyzer — Analyzes tracebacks, errors, and test failures to isolate root cause bugs.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("loopix.repair.root_cause_analyzer")


@dataclass
class FailureRootCause:
    probable_cause: str
    target_file: str
    target_line: int
    error_type: str


class RootCauseAnalyzer:
    """Parses verification output/stack traces to locate breaking changes."""

    def analyze_failure(self, traceback_text: str) -> FailureRootCause | None:
        """Rule-based parsing of stack traces to identify error type and file location."""
        # Look for typical python traceback line: File "path", line X, in Y
        match = re.search(r'File\s+"([^"]+)",\s+line\s+(\d+)', traceback_text)
        if not match:
            return None

        file_path = match.group(1)
        line_num = int(match.group(2))

        # Infer error type
        err_type = "UnknownError"
        type_match = re.search(r'(\w+Error):\s+(.*)', traceback_text)
        if type_match:
            err_type = type_match.group(1)

        cause = f"Found {err_type} stack trace entry at line {line_num} in '{file_path}'"
        
        logger.info(f"Isolated root cause: {cause}")
        return FailureRootCause(
            probable_cause=cause,
            target_file=file_path,
            target_line=line_num,
            error_type=err_type
        )


# ── Singleton ───────────────────────────────────────────────────────────────

root_cause_analyzer = RootCauseAnalyzer()
