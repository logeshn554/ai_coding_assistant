"""
Failure classification and recovery system.

Classifies failures and determines recovery strategy:
  - LLM_ERROR: Retry with different prompt
  - RATE_LIMIT: Backoff and retry
  - TOOL_ERROR: Fix and retry
  - CODE_ERROR: Repair and retry
  - TEST_FAILURE: Debug and retry
  - STUCK: Stop and escalate
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass
import hashlib


class FailureType(str, Enum):
    """Classification of failure types."""
    LLM_ERROR = "llm_error"
    RATE_LIMIT = "rate_limit"
    TOOL_ERROR = "tool_error"
    TOOL_TIMEOUT = "tool_timeout"
    CODE_ERROR = "code_error"
    TEST_FAILURE = "test_failure"
    DEPENDENCY_ERROR = "dependency_error"
    WORKSPACE_ERROR = "workspace_error"
    PERMISSION_ERROR = "permission_error"
    NETWORK_ERROR = "network_error"
    MERGE_CONFLICT = "merge_conflict"
    STUCK = "stuck"
    UNKNOWN = "unknown"


class RecoveryStrategy(str, Enum):
    """Recovery strategy for a failure."""
    RETRY = "retry"
    REPAIR = "repair"
    SWITCH_MODEL = "switch_model"
    SWITCH_AGENT = "switch_agent"
    RECREATE_WORKSPACE = "recreate_workspace"
    ASK_USER = "ask_user"
    ABORT = "abort"


@dataclass
class FailureFingerprint:
    """Fingerprint to detect repeated failures."""
    failure_type: str
    normalized_error: str
    file_path: Optional[str]
    line_number: Optional[int]
    command: Optional[str]

    def hash(self) -> str:
        """Get consistent hash of fingerprint."""
        content = f"{self.failure_type}:{self.normalized_error}:{self.file_path}:{self.line_number}:{self.command}"
        return hashlib.sha256(content.encode()).hexdigest()

    def __hash__(self):
        return hash(self.hash())

    def __eq__(self, other):
        if not isinstance(other, FailureFingerprint):
            return False
        return self.hash() == other.hash()


class FailureClassifier:
    """Classify failures and determine recovery."""

    @staticmethod
    def classify(error_message: str, context: Optional[dict] = None) -> FailureType:
        """
        Classify an error into a FailureType.

        Args:
            error_message: Error message to classify
            context: Optional context (tool_name, exit_code, etc.)

        Returns:
            FailureType classification
        """
        error_lower = error_message.lower()
        context = context or {}

        # Rate limiting
        if any(phrase in error_lower for phrase in [
            "rate limit",
            "too many requests",
            "quota",
            "throttle",
        ]):
            return FailureType.RATE_LIMIT

        # Timeout
        if any(phrase in error_lower for phrase in [
            "timeout",
            "timed out",
            "deadline",
            "took too long",
        ]):
            return FailureType.TOOL_TIMEOUT

        # Permission
        if any(phrase in error_lower for phrase in [
            "permission denied",
            "permission error",
            "access denied",
            "unauthorized",
            "forbidden",
        ]):
            return FailureType.PERMISSION_ERROR

        # Network
        if any(phrase in error_lower for phrase in [
            "network",
            "connection",
            "socket",
            "dns",
            "host not found",
        ]):
            return FailureType.NETWORK_ERROR

        # Workspace
        if any(phrase in error_lower for phrase in [
            "workspace",
            "directory",
            "disk space",
            "not found",
            "no such file",
        ]):
            return FailureType.WORKSPACE_ERROR

        # Test failure
        if context.get("tool_name") == "run_tests":
            if "failed" in error_lower or "error" in error_lower:
                return FailureType.TEST_FAILURE

        # Merge conflict
        if "merge conflict" in error_lower or "conflict" in error_lower:
            return FailureType.MERGE_CONFLICT

        # Dependency
        if any(phrase in error_lower for phrase in [
            "dependency",
            "import error",
            "module not found",
            "no module named",
        ]):
            return FailureType.DEPENDENCY_ERROR

        # Code error
        if any(phrase in error_lower for phrase in [
            "syntaxerror",
            "syntax error",
            "typeerror",
            "type error",
            "runtimeerror",
            "runtime error",
            "attributeerror",
            "nameerror",
            "valueerror",
            "indentationerror",
            "traceback",
        ]):
            return FailureType.CODE_ERROR

        # Tool error
        if context.get("tool_name"):
            return FailureType.TOOL_ERROR

        # LLM error
        if context.get("source") == "llm":
            return FailureType.LLM_ERROR

        return FailureType.UNKNOWN

    @staticmethod
    def get_recovery_strategy(failure_type: FailureType) -> RecoveryStrategy:
        """Get recommended recovery strategy for a failure type."""
        strategies = {
            FailureType.LLM_ERROR: RecoveryStrategy.RETRY,
            FailureType.RATE_LIMIT: RecoveryStrategy.RETRY,
            FailureType.TOOL_ERROR: RecoveryStrategy.RETRY,
            FailureType.TOOL_TIMEOUT: RecoveryStrategy.RETRY,
            FailureType.CODE_ERROR: RecoveryStrategy.REPAIR,
            FailureType.TEST_FAILURE: RecoveryStrategy.REPAIR,
            FailureType.DEPENDENCY_ERROR: RecoveryStrategy.RECREATE_WORKSPACE,
            FailureType.WORKSPACE_ERROR: RecoveryStrategy.RECREATE_WORKSPACE,
            FailureType.PERMISSION_ERROR: RecoveryStrategy.ASK_USER,
            FailureType.NETWORK_ERROR: RecoveryStrategy.RETRY,
            FailureType.MERGE_CONFLICT: RecoveryStrategy.ASK_USER,
            FailureType.STUCK: RecoveryStrategy.ABORT,
            FailureType.UNKNOWN: RecoveryStrategy.RETRY,
        }
        return strategies.get(failure_type, RecoveryStrategy.RETRY)

    @staticmethod
    def create_fingerprint(
        failure_type: FailureType,
        error_message: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        command: Optional[str] = None,
    ) -> FailureFingerprint:
        """Create a fingerprint for a failure."""
        # Normalize error message (remove changing parts)
        normalized = FailureClassifier._normalize_error(error_message)

        return FailureFingerprint(
            failure_type=str(failure_type),
            normalized_error=normalized,
            file_path=file_path,
            line_number=line_number,
            command=command,
        )

    @staticmethod
    def _normalize_error(error_message: str) -> str:
        """Normalize error message for comparison."""
        # Remove timestamps, file paths, specific values
        import re

        normalized = error_message.lower()

        # Remove timestamps
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}", "TIMESTAMP", normalized)

        # Remove file paths
        normalized = re.sub(r"[/\\][^\s:]+\.[a-z]+", "FILEPATH", normalized)

        # Remove line numbers
        normalized = re.sub(r"line \d+", "line N", normalized)

        # Remove specific numbers
        normalized = re.sub(r"\d+", "N", normalized)

        return normalized[:200]  # Limit length


class StuckDetector:
    """Detect when an agent is stuck in a loop."""

    def __init__(self, max_repeated_failures: int = 3):
        """
        Initialize stuck detector.

        Args:
            max_repeated_failures: Maximum repeated same failures before marking stuck
        """
        self.max_repeated_failures = max_repeated_failures
        self.failure_history: dict = {}

    def record_failure(self, fingerprint: FailureFingerprint) -> bool:
        """
        Record a failure and check if stuck.

        Args:
            fingerprint: Failure fingerprint

        Returns:
            True if stuck (same failure repeated too many times)
        """
        fp_hash = fingerprint.hash()

        if fp_hash not in self.failure_history:
            self.failure_history[fp_hash] = []

        self.failure_history[fp_hash].append(fingerprint)

        # Check if repeated too many times
        if len(self.failure_history[fp_hash]) >= self.max_repeated_failures:
            return True

        return False

    def get_status(self) -> dict:
        """Get detector status."""
        return {
            "total_unique_failures": len(self.failure_history),
            "repeated_failures": {
                k: len(v) for k, v in self.failure_history.items()
                if len(v) > 1
            },
        }

    def reset(self) -> None:
        """Reset detector."""
        self.failure_history.clear()
