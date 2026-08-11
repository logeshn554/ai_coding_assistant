"""
Unified agent system with real LLM loops, state machines, and tool execution.

This package provides:
  - IAgent: Unified interface all agents implement
  - AgentStateMachine: Validated state transitions
  - BaseAgent: Reference implementation with real LLM loop
  - ToolValidator, ToolExecutor: Tool validation and execution
  - LLMIntegration: Real LLM provider integration
"""

from .interfaces import (
    AgentState,
    IAgent,
    IAgentFactory,
    ILLMIntegration,
    IToolExecutor,
    IToolValidator,
    AgentContext,
    AgentResult,
    LLMMessage,
    Task,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolCallError,
)

from .state_machine import AgentStateMachine, VALID_TRANSITIONS, TERMINAL_STATES

from .base_agent import BaseAgent

from .tool_layer import ToolExecutor, ToolValidator, PathValidator

from .llm_integration import LLMIntegration

from .tool_registry import ToolRegistry

from .agent_factory import AgentFactory

from .workspace import Workspace, WorkspaceManager, WorkspaceHealth

from .event_system import EventBus, Event, EventType, Progress

from .dag_executor import DAGExecutor, TaskGraphValidator, DAGError

from .verification_engine import VerificationEngine, VerificationResult, CheckResult, CheckStatus

from .failure_handling import (
    FailureClassifier, FailureType, RecoveryStrategy,
    FailureFingerprint, StuckDetector
)

from .checkpoint_manager import CheckpointManager, ExecutionReplayer

from .git_worktree_manager import GitWorktreeManager, WorktreeInfo

from .cost_tracker import CostTracker, AgentBudget, CostEntry, CostType

__all__ = [
    "AgentState",
    "IAgent",
    "IAgentFactory",
    "ILLMIntegration",
    "IToolExecutor",
    "IToolValidator",
    "AgentContext",
    "AgentResult",
    "LLMMessage",
    "Task",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
    "ToolCallError",
    "AgentStateMachine",
    "VALID_TRANSITIONS",
    "TERMINAL_STATES",
    "BaseAgent",
    "ToolExecutor",
    "ToolValidator",
    "PathValidator",
    "LLMIntegration",
    "ToolRegistry",
    "AgentFactory",
    "Workspace",
    "WorkspaceManager",
    "WorkspaceHealth",
    "EventBus",
    "Event",
    "EventType",
    "Progress",
    "DAGExecutor",
    "TaskGraphValidator",
    "DAGError",
    "VerificationEngine",
    "VerificationResult",
    "CheckResult",
    "CheckStatus",
    "FailureClassifier",
    "FailureType",
    "RecoveryStrategy",
    "FailureFingerprint",
    "StuckDetector",
    "CheckpointManager",
    "ExecutionReplayer",
    "GitWorktreeManager",
    "WorktreeInfo",
    "CostTracker",
    "AgentBudget",
    "CostEntry",
    "CostType",
]
