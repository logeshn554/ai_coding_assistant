"""
Agent Runtime — The single canonical execution engine for all AI coding actions.
"""

from .events import AgentEvent
from .llm_adapter import ModelResponse, ModelResponseNormalizer, ToolCall
from .runtime import (
    AgentResult,
    AgentRuntime,
    AgentSessionState,
    AgentState,
    AgentTask,
    InvalidStateTransitionError,
    VerificationStatus,
)
from .tool_executor import ToolExecutionRecord, ToolExecutor, ToolResult
from .transactional_workspace import ChangeSet, FileSnapshot, TransactionalWorkspace

__all__ = [
    "AgentRuntime",
    "AgentState",
    "AgentSessionState",
    "AgentTask",
    "AgentResult",
    "VerificationStatus",
    "InvalidStateTransitionError",
    "ToolExecutor",
    "ToolResult",
    "ToolExecutionRecord",
    "ModelResponse",
    "ToolCall",
    "ModelResponseNormalizer",
    "AgentEvent",
    "TransactionalWorkspace",
    "ChangeSet",
    "FileSnapshot",
]
