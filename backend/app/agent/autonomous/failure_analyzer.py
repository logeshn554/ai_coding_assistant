"""
Failure Analyzer & Error Classifier — Step 9, 10 requirements.

Parses raw verification and terminal outputs into strongly typed VerificationFailure
objects and maps failure details into ContextEngine search parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureCategory(str, Enum):
    SYNTAX = "SYNTAX"
    TYPE_ERROR = "TYPE_ERROR"
    LINT = "LINT"
    UNIT_TEST = "UNIT_TEST"
    INTEGRATION_TEST = "INTEGRATION_TEST"
    BUILD = "BUILD"
    RUNTIME = "RUNTIME"
    DEPENDENCY = "DEPENDENCY"
    CONFIGURATION = "CONFIGURATION"
    ENVIRONMENT = "ENVIRONMENT"
    UNKNOWN = "UNKNOWN"


@dataclass
class VerificationFailure:
    """Structured representation of a verification failure."""
    command: str
    category: FailureCategory
    file: str | None = None
    line: int | None = None
    column: int | None = None
    message: str = ""
    stack_trace: str | None = None
    related_symbols: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "category": self.category.value,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "related_symbols": self.related_symbols,
        }


class FailureAnalyzer:
    """Classifies raw test/build failure logs into structured VerificationFailure objects."""

    @classmethod
    def analyze_output(cls, command: str, output: str) -> VerificationFailure:
        category = FailureCategory.UNKNOWN
        file_path = None
        line_num = None
        message = output[:300] if output else "Verification failed"
        symbols = []

        out_lower = output.lower()

        # Category classification
        if "syntaxerror" in out_lower or "indented block" in out_lower:
            category = FailureCategory.SYNTAX
        elif "typeerror" in out_lower or "ts" in out_lower and "error" in out_lower:
            category = FailureCategory.TYPE_ERROR
        elif "assertionerror" in out_lower or "failed" in out_lower or "assert" in out_lower:
            category = FailureCategory.UNIT_TEST
        elif "module_not_found" in out_lower or "import error" in out_lower or "cannot find module" in out_lower:
            category = FailureCategory.DEPENDENCY

        # Extract file and line from traceback patterns like "File 'src/auth.py', line 42"
        file_match = re.search(r'File "([^"]+)", line (\d+)', output)
        if not file_match:
            file_match = re.search(r'([A-Za-z0-9_/\.\-]+\.(?:py|ts|tsx|js|jsx)):(\d+)', output)

        if file_match:
            file_path = file_match.group(1)
            line_num = int(file_match.group(2))

        # Extract symbol candidates
        sym_match = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", output)
        symbols = list(set([s for s in sym_match if s.lower() not in {"file", "line", "test", "assert", "error", "failed", "passed"}]))[:5]

        return VerificationFailure(
            command=command,
            category=category,
            file=file_path,
            line=line_num,
            message=message,
            stack_trace=output[:1000] if output else None,
            related_symbols=symbols,
        )
