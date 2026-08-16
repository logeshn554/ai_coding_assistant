"""
Unified agent system with real LLM loops, state machines, and tool execution.

This package provides:
  - IAgent: Unified interface all agents implement
  - AgentStateMachine: Validated state transitions
  - BaseAgent: Reference implementation with real LLM loop
  - ToolValidator, ToolExecutor: Tool validation and execution
  - LLMIntegration: Real LLM provider integration
"""

from .agent_factory import AgentFactory
from .base_agent import BaseAgent
from .checkpoint_manager import CheckpointManager, ExecutionReplayer
from .cost_tracker import AgentBudget, CostEntry, CostTracker, CostType
from .dag_executor import DAGError, DAGExecutor, TaskGraphValidator
from .event_system import Event, EventBus, EventType, Progress
from .failure_handling import (
    FailureClassifier,
    FailureFingerprint,
    FailureType,
    RecoveryStrategy,
    StuckDetector,
)
from .git_worktree_manager import GitWorktreeManager, WorktreeInfo
from .interfaces import (
    AgentContext,
    AgentResult,
    AgentState,
    IAgent,
    IAgentFactory,
    ILLMIntegration,
    IToolExecutor,
    IToolValidator,
    LLMMessage,
    Task,
    ToolCall,
    ToolCallError,
    ToolDefinition,
    ToolResult,
)
from .llm_integration import LLMIntegration
from .state_machine import TERMINAL_STATES, VALID_TRANSITIONS, AgentStateMachine
from .tool_layer import PathValidator, ToolExecutor, ToolValidator
from .tool_registry import ToolRegistry
from .verification_engine import (
    CheckResult,
    CheckStatus,
    VerificationEngine,
    VerificationResult,
)
from .workspace import Workspace, WorkspaceHealth, WorkspaceManager

__all__ = [
    "TERMINAL_STATES",
    "VALID_TRANSITIONS",
    "AgentBudget",
    "AgentContext",
    "AgentFactory",
    "AgentResult",
    "AgentState",
    "AgentStateMachine",
    "BaseAgent",
    "CheckResult",
    "CheckStatus",
    "CheckpointManager",
    "CostEntry",
    "CostTracker",
    "CostType",
    "DAGError",
    "DAGExecutor",
    "Event",
    "EventBus",
    "EventType",
    "ExecutionReplayer",
    "FailureClassifier",
    "FailureFingerprint",
    "FailureType",
    "GitWorktreeManager",
    "IAgent",
    "IAgentFactory",
    "ILLMIntegration",
    "IToolExecutor",
    "IToolValidator",
    "LLMIntegration",
    "LLMMessage",
    "PathValidator",
    "Progress",
    "RecoveryStrategy",
    "StuckDetector",
    "Task",
    "TaskGraphValidator",
    "ToolCall",
    "ToolCallError",
    "ToolDefinition",
    "ToolExecutor",
    "ToolRegistry",
    "ToolResult",
    "ToolValidator",
    "VerificationEngine",
    "VerificationResult",
    "Workspace",
    "WorkspaceHealth",
    "WorkspaceManager",
    "WorktreeInfo",
]
