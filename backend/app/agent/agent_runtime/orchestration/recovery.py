"""
Recovery & Self-Healing Engine — Classifies execution failures and routes recovery actions.

Provides a unified FailureClassifier and RecoverySelector to dynamically
handle API timeouts, linter exceptions, test failures, permissions,
and infinite loops.
"""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("agent_runtime.orchestration.recovery")


class FailureType(str, Enum):
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    CODE_ERROR = "code_error"
    TEST_FAILURE = "test_failure"
    DEPENDENCY_ERROR = "dependency_error"
    ENVIRONMENT_ERROR = "environment_error"
    NETWORK_ERROR = "network_error"
    PERMISSION_ERROR = "permission_error"
    WORKSPACE_ERROR = "workspace_error"
    STUCK_ERROR = "stuck_error"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    RETRY = "retry"
    REPAIR = "repair"
    SWITCH_MODEL = "switch_model"
    SWITCH_AGENT = "switch_agent"
    RECREATE_WORKSPACE = "recreate_workspace"
    ASK_HUMAN = "ask_human"
    ABORT = "abort"


@dataclass
class FailureReport:
    failure_type: FailureType
    severity: str  # "low", "medium", "high", "critical"
    message: str
    raw_error: Optional[Exception] = None
    details: dict[str, Any] = None


class FailureClassifier:
    """Classifies failures into granular types based on stdout/stderr, error messages, and context."""

    def classify(self, error: Exception | str, context: Optional[dict[str, Any]] = None) -> FailureReport:
        err_msg = str(error)
        ctx = context or {}
        
        # 1. Parse exceptions / messages
        if "TimeoutError" in err_msg or "time out" in err_msg.lower():
            return FailureReport(
                failure_type=FailureType.MODEL_ERROR if "llm" in err_msg.lower() else FailureType.WORKSPACE_ERROR,
                severity="medium",
                message=f"Timeout occurred: {err_msg}",
                raw_error=error if isinstance(error, Exception) else None,
            )
            
        if "RateLimitError" in err_msg or "rate limit" in err_msg.lower() or "429" in err_msg:
            return FailureReport(
                failure_type=FailureType.NETWORK_ERROR,
                severity="medium",
                message="LLM provider rate limit hit.",
                raw_error=error if isinstance(error, Exception) else None,
            )

        if "PermissionError" in err_msg or "permission denied" in err_msg.lower():
            return FailureReport(
                failure_type=FailureType.PERMISSION_ERROR,
                severity="high",
                message=f"Access denied: {err_msg}",
                raw_error=error if isinstance(error, Exception) else None,
            )

        if "SyntaxError" in err_msg or "invalid syntax" in err_msg.lower() or "PatchSyntaxError" in err_msg:
            return FailureReport(
                failure_type=FailureType.CODE_ERROR,
                severity="low",
                message="Syntax error in generated code.",
                raw_error=error if isinstance(error, Exception) else None,
            )

        if "pytest" in err_msg.lower() or "test failure" in err_msg.lower() or ctx.get("test_failures", 0) > 0:
            return FailureReport(
                failure_type=FailureType.TEST_FAILURE,
                severity="low",
                message="Unit tests or verification checks failed.",
                raw_error=error if isinstance(error, Exception) else None,
                details=ctx,
            )

        if "docker" in err_msg.lower() or "container" in err_msg.lower():
            return FailureReport(
                failure_type=FailureType.WORKSPACE_ERROR,
                severity="high",
                message="Docker or workspace environment failure.",
                raw_error=error if isinstance(error, Exception) else None,
            )

        if "depends_on" in err_msg.lower() or "dependency" in err_msg.lower():
            return FailureReport(
                failure_type=FailureType.DEPENDENCY_ERROR,
                severity="high",
                message="Task graph dependency resolution error.",
                raw_error=error if isinstance(error, Exception) else None,
            )

        if "stuck" in err_msg.lower() or "loop" in err_msg.lower():
            return FailureReport(
                failure_type=FailureType.STUCK_ERROR,
                severity="high",
                message="Agent got stuck in a repetitive loop.",
                raw_error=error if isinstance(error, Exception) else None,
            )

        # Catch-all fallback classification
        return FailureReport(
            failure_type=FailureType.UNKNOWN,
            severity="medium",
            message=err_msg,
            raw_error=error if isinstance(error, Exception) else None,
        )


class RecoverySelector:
    """Selects the best self-healing path based on failure type, attempt count, and budget limits."""

    def select_action(self, report: FailureReport, attempt: int, max_retries: int = 3) -> RecoveryAction:
        logger.info(f"Selecting recovery for type={report.failure_type.value}, attempt={attempt}/{max_retries}")

        if attempt >= max_retries:
            return RecoveryAction.ABORT

        # Recovery logic matrix
        if report.failure_type == FailureType.NETWORK_ERROR:
            # Switch LLM provider or back off
            return RecoveryAction.SWITCH_MODEL if attempt > 1 else RecoveryAction.RETRY

        if report.failure_type == FailureType.MODEL_ERROR:
            return RecoveryAction.SWITCH_MODEL

        if report.failure_type == FailureType.CODE_ERROR:
            return RecoveryAction.REPAIR  # Route code errors back to repair handler

        if report.failure_type == FailureType.TEST_FAILURE:
            return RecoveryAction.REPAIR

        if report.failure_type == FailureType.PERMISSION_ERROR:
            return RecoveryAction.ASK_HUMAN

        if report.failure_type == FailureType.WORKSPACE_ERROR:
            return RecoveryAction.RECREATE_WORKSPACE

        if report.failure_type == FailureType.STUCK_ERROR:
            return RecoveryAction.REPAIR  # Re-route stuck agent with loop feedback to self-correct

        return RecoveryAction.RETRY
