"""
Phase 12: AI-Native Developer Experience & Contextual Action Router.

Routes contextual quick actions (Explain, Optimize, Refactor, Generate Tests, Fix Error, Review)
and natural-language queries through existing specialized subsystems.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionContextType(str, Enum):
    FUNCTION = "function"
    ERROR = "error"
    TEST_FAILURE = "test_failure"
    GIT_DIFF = "git_diff"
    GENERAL = "general"


@dataclass
class ContextualActionRequest:
    action_type: str  # explain | optimize | refactor | generate_tests | fix_error | review
    context_type: ActionContextType
    target_code: str | None = None
    file_path: str | None = None
    line_no: int | None = None
    error_message: str | None = None


class ActionRouter:
    """Routes contextual IDE quick actions to specialized backend engines."""

    @classmethod
    def route_action(cls, request: ContextualActionRequest) -> dict[str, Any]:
        act = request.action_type.lower().strip()

        if act == "explain":
            return {
                "target_subsystem": "ContextEngine",
                "prompt": f"Explain the code logic in {request.file_path or 'selected file'}.",
                "mode": "Ask",
            }
        elif act in ("optimize", "refactor"):
            return {
                "target_subsystem": "AgentRuntime",
                "prompt": f"Refactor and optimize implementation in {request.file_path or 'selected code'}.",
                "mode": "Edit",
            }
        elif act == "generate_tests":
            return {
                "target_subsystem": "QualityEngine",
                "prompt": f"Generate unit tests for function in {request.file_path or 'selected target'}.",
                "mode": "Agent",
            }
        elif act == "fix_error":
            return {
                "target_subsystem": "AIDebugger",
                "prompt": f"Analyze and repair error: {request.error_message or 'failing diagnostic'}.",
                "mode": "Agent",
            }
        elif act == "review":
            return {
                "target_subsystem": "GitCollaborationEngine",
                "prompt": "Review working tree diff changes and verify criteria.",
                "mode": "Agent",
            }

        return {
            "target_subsystem": "AgentRuntime",
            "prompt": f"Execute natural language request: {act}",
            "mode": "Agent",
        }
