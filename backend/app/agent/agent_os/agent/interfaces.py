"""
Unified agent interface for all agent types.

This module defines the core abstractions that all agents must implement,
regardless of execution model (sync, async, local, Docker).

The agent loop pattern:
  1. Agent receives task with allowed_paths and acceptance_criteria
  2. Agent builds context from workspace
  3. Agent calls LLM with tools available
  4. LLM responds with tool calls or completion
  5. Agent validates and authorizes tool calls
  6. Agent executes tools and captures results
  7. Agent observes results and continues loop
  8. Agent claims completion
  9. Independent verification system verifies result
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentState(str, Enum):
    """Agent lifecycle states."""
    CREATED = "created"
    INITIALIZING = "initializing"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    WAITING_FOR_LLM = "waiting_for_llm"
    WAITING_FOR_TOOL = "waiting_for_tool"
    EXECUTING_TOOL = "executing_tool"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"


class ToolCallError(Exception):
    """Error from tool invocation."""


@dataclass
class ToolDefinition:
    """Complete tool definition with schema and metadata."""
    name: str
    description: str
    input_schema: dict[str, Any]
    executor: Callable[..., Any]
    timeout_seconds: int = 30
    permission_level: str = "user"  # user, admin, internal
    risk_level: str = "low"  # low, medium, high
    requires_approval: bool = False
    batch_size: int = 1


@dataclass
class ToolCall:
    """A single tool invocation request from the LLM."""
    tool_name: str
    arguments: dict[str, Any]
    tool_call_id: str  # Unique ID for this call
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_call_id: str
    tool_name: str
    status: str  # success, error, timeout, permission_denied, validation_error
    result: Any
    error: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: float = 0.0


@dataclass
class LLMMessage:
    """Message in the agent-LLM conversation."""
    role: str  # system, user, assistant
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class Task:
    """Execution task with constraints and acceptance criteria."""
    task_id: str
    title: str
    description: str
    agent_type: str  # coding, testing, review, etc.
    depends_on: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)  # Restrict writes to these paths
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_paths(self) -> tuple[bool, list[str]]:
        """
        Validate that allowed_paths are valid.
        
        Returns:
            (is_valid, list of errors)
        """
        errors = []
        
        if not self.allowed_paths:
            errors.append(f"Task {self.task_id} has no allowed_paths defined")
        
        for path in self.allowed_paths:
            if not isinstance(path, str) or not path.strip():
                errors.append(f"Invalid allowed_path: {path}")
        
        return len(errors) == 0, errors


@dataclass
class AgentContext:
    """Context provided to agent at start."""
    run_id: str
    task: Task
    workspace_root: str
    attempt_id: str = ""
    execution_id: str = ""
    model_provider: str | None = None
    model_name: str | None = None
    budget_tokens: int = 8000
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of agent execution."""
    run_id: str
    agent_id: str
    task_id: str
    attempt_id: str
    status: str  # success, failed, cancelled, timeout, blocked
    final_state: AgentState
    summary: str
    files_changed: list[str] = field(default_factory=list)
    tool_calls_total: int = 0
    tool_calls_succeeded: int = 0
    tool_calls_failed: int = 0
    llm_calls: int = 0
    tokens_used: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    verification_results: dict[str, Any] = field(default_factory=dict)


class IAgent(ABC):
    """
    Base agent interface for all agent implementations.
    
    The agent lifecycle:
      CREATED → INITIALIZING → PLANNING → READY → 
      RUNNING → WAITING_FOR_LLM → (tool calls?) → 
      WAITING_FOR_TOOL → EXECUTING_TOOL → OBSERVING → 
      (repeat or VERIFYING) → REPAIRING? → COMPLETED/FAILED
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique agent identifier."""

    @property
    @abstractmethod
    def current_state(self) -> AgentState:
        """Current agent state."""

    @abstractmethod
    async def initialize(self, context: AgentContext) -> None:
        """Initialize agent with context and transition to READY."""

    @abstractmethod
    async def get_available_tools(self) -> dict[str, ToolDefinition]:
        """Return tools this agent can use."""

    @abstractmethod
    async def execute(self) -> AgentResult:
        """
        Execute the agent loop until completion or failure.
        
        The loop:
          1. Build context (files, workspace state)
          2. Call LLM with tools
          3. Receive response with tool calls or completion
          4. Validate tool calls
          5. Execute tools
          6. Capture results as observations
          7. Append to conversation history
          8. Repeat until agent claims completion
          9. Claim completion
          
        Then independent verification happens outside the agent loop.
        """

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel execution and cleanup."""

    @abstractmethod
    def get_execution_log(self) -> list[dict[str, Any]]:
        """Return detailed execution log for observability."""


class IAgentFactory(ABC):
    """Factory for creating agents based on type."""

    @abstractmethod
    async def create_agent(self, agent_type: str) -> IAgent:
        """Create an agent of the given type."""

    @abstractmethod
    def get_supported_types(self) -> list[str]:
        """Return list of supported agent types."""


class IToolExecutor(ABC):
    """Executes validated tool calls."""

    @abstractmethod
    async def execute(self, tool_call: ToolCall, allowed_paths: list[str]) -> ToolResult:
        """
        Execute a tool call.
        
        Args:
            tool_call: The tool call to execute
            allowed_paths: List of paths this task is allowed to modify
            
        Returns:
            ToolResult with outcome
            
        Raises:
            ToolCallError if validation or execution fails
        """


class IToolValidator(ABC):
    """Validates tool calls before execution."""

    @abstractmethod
    async def validate(
        self,
        tool_call: ToolCall,
        tool_def: ToolDefinition,
        allowed_paths: list[str]
    ) -> tuple[bool, str | None]:
        """
        Validate a tool call.
        
        Returns:
            (is_valid, error_message)
            
        Checks:
          - Schema compliance
          - Argument types
          - Path validation (within allowed_paths)
          - Permission level
          - Timeout feasibility
        """


class ILLMIntegration(ABC):
    """Integration with LLM for agent reasoning."""

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: dict[str, ToolDefinition],
        max_tokens: int = 2000,
    ) -> LLMMessage:
        """
        Call LLM with tools available.
        
        Returns:
            LLMMessage with response and any tool_calls
        """

    @abstractmethod
    async def cancel_request(self, request_id: str) -> None:
        """Cancel an in-flight LLM request."""


class IAgentStateManager(ABC):
    """Manages agent state transitions with validation."""

    @abstractmethod
    def transition(self, new_state: AgentState) -> None:
        """Transition to new state."""

    @abstractmethod
    def can_transition_to(self, new_state: AgentState) -> tuple[bool, str | None]:
        """Check if transition is valid."""

    @abstractmethod
    def get_history(self) -> list[tuple[AgentState, float]]:
        """Get state transition history."""
