"""
Base agent implementation with real LLM loop.

This is the core reasoning loop:
  1. Build context from workspace
  2. Call LLM with available tools
  3. Get response with tool calls or completion claim
  4. Validate and execute tool calls
  5. Observe results
  6. Repeat or claim completion
  7. Return to orchestrator for independent verification
"""

import asyncio
import uuid
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from .interfaces import (
    IAgent,
    AgentContext,
    AgentResult,
    AgentState,
    LLMMessage,
    ToolCall,
    ToolDefinition,
    Task,
)
from .state_machine import AgentStateMachine
from .tool_layer import ToolExecutor, ToolValidator
from .llm_integration import LLMIntegration
from .workspace import Workspace


class BaseAgent(IAgent):
    """
    Base agent implementation with real LLM loop and state management.

    The agent loop:
      1. READY state
      2. Enter RUNNING
      3. Transition WAITING_FOR_LLM
      4. Call LLM with tools
      5. Get response with tool calls (if any)
      6. Transition WAITING_FOR_TOOL
      7. Transition EXECUTING_TOOL
      8. Execute all tool calls
      9. Transition OBSERVING
      10. Append observations to history
      11. Go back to RUNNING (step 3) or VERIFYING
      12. Agent claims completion
      13. Transition VERIFYING (actually handled by orchestrator)
      14. Return result
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        model_router,
        tools_registry: Optional[Dict[str, ToolDefinition]] = None,
    ):
        self.agent_id_val = agent_id
        self.agent_type = agent_type
        self.model_router = model_router
        self.tools_registry = tools_registry or {}

        self._state_machine = AgentStateMachine(AgentState.CREATED)
        self._llm_integration = LLMIntegration(model_router)
        self._tool_executor = None  # Will be initialized in initialize()
        self._tool_validator = ToolValidator()

        self._context: Optional[AgentContext] = None
        self._conversation_history: List[LLMMessage] = []
        self._execution_log: List[Dict[str, Any]] = []
        self._start_time: Optional[float] = None
        self._workspace: Optional[Workspace] = None
        self._tool_calls_total = 0
        self._tool_calls_succeeded = 0
        self._tool_calls_failed = 0
        self._llm_calls = 0
        self._tokens_used = 0

    @property
    def agent_id(self) -> str:
        return self.agent_id_val

    @property
    def current_state(self) -> AgentState:
        return self._state_machine.current_state

    async def initialize(self, context: AgentContext) -> None:
        """Initialize agent with context."""
        self._state_machine.transition(AgentState.INITIALIZING, "initialize called")
        self._context = context
        self._start_time = time.time()

        # Initialize workspace
        self._workspace = Workspace(context.workspace_root)
        success, message = await self._workspace.initialize()
        if not success:
            self._add_log("WORKSPACE_INIT_ERROR", {"error": message})
            raise RuntimeError(f"Failed to initialize workspace: {message}")

        # Initialize tool executor with workspace root
        self._tool_executor = ToolExecutor(self.tools_registry, context.workspace_root)

        # Log initialization
        self._add_log("INITIALIZE", {"context": context.__dict__, "workspace": self._workspace.get_status()})

        self._state_machine.transition(AgentState.PLANNING, "initialization complete")

    async def get_available_tools(self) -> Dict[str, ToolDefinition]:
        """Return tools this agent can use."""
        return self.tools_registry

    async def execute(self) -> AgentResult:
        """
        Execute the agent loop until completion or failure.

        Returns result with files changed, tool calls made, etc.
        """
        if not self._context:
            raise RuntimeError("Agent not initialized")

        try:
            self._state_machine.transition(AgentState.READY, "execute started")

            # Main agent loop
            while not self._state_machine.is_terminal():
                # Enter running state
                self._state_machine.transition(AgentState.RUNNING, "loop iteration")

                # Try to call LLM
                success = await self._llm_reasoning_step()
                if not success:
                    self._state_machine.transition(
                        AgentState.FAILED, "LLM reasoning failed"
                    )
                    break

                # Check if agent claimed completion
                if self._should_complete():
                    self._state_machine.transition(
                        AgentState.VERIFYING, "agent claimed completion"
                    )
                    break

                # Avoid infinite loops
                if len(self._conversation_history) > 20:
                    self._state_machine.transition(
                        AgentState.TIMEOUT, "max conversation turns exceeded"
                    )
                    break

            # Build result
            return self._build_result()

        except Exception as e:
            self._add_log("ERROR", {"error": str(e)})
            self._state_machine.transition(AgentState.FAILED, f"exception: {str(e)}")
            return self._build_result()

    async def cancel(self) -> None:
        """Cancel execution."""
        self._state_machine.transition(AgentState.CANCELLED, "cancel requested")
        if self._workspace:
            self._workspace.cleanup()
        self._add_log("CANCELLED", {})

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Return detailed execution log."""
        return self._execution_log

    # --- Private Methods ---

    async def _llm_reasoning_step(self) -> bool:
        """
        Single LLM reasoning step.

        1. Build context
        2. Call LLM with tools
        3. Execute tool calls if any
        4. Append observations
        5. Return True if successful
        """
        try:
            # Build context for LLM
            self._state_machine.transition(
                AgentState.WAITING_FOR_LLM, "calling LLM"
            )

            context_text = self._build_context()
            self._conversation_history.append(
                LLMMessage(role="user", content=context_text)
            )

            # Call LLM
            self._add_log("LLM_CALL", {"context": context_text[:200]})
            self._llm_calls += 1

            response = await self._llm_integration.generate_with_tools(
                self._conversation_history, self.tools_registry, max_tokens=2000
            )

            self._conversation_history.append(response)
            self._add_log("LLM_RESPONSE", {"content": response.content[:200]})

            # Execute tool calls if any
            if response.tool_calls:
                self._state_machine.transition(
                    AgentState.WAITING_FOR_TOOL, "LLM requested tool calls"
                )

                tool_results = await self._execute_tool_calls(response.tool_calls)

                # Add tool results to conversation
                observation = LLMMessage(
                    role="user",
                    content="Tool execution complete. See results below.",
                    tool_results=tool_results,
                )
                self._conversation_history.append(observation)
                self._add_log("TOOL_EXECUTION_COMPLETE", {"results": len(tool_results)})

                self._state_machine.transition(AgentState.OBSERVING, "observing tool results")

            return True

        except Exception as e:
            self._add_log("LLM_STEP_ERROR", {"error": str(e)})
            return False

    async def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List:
        """Execute all tool calls and return results."""
        self._state_machine.transition(AgentState.EXECUTING_TOOL, "executing tools")

        results = []
        for tool_call in tool_calls:
            self._tool_calls_total += 1
            self._add_log("TOOL_CALL", {"tool": tool_call.tool_name, "id": tool_call.tool_call_id})

            result = await self._tool_executor.execute(
                tool_call, self._context.task.allowed_paths
            )

            results.append(result)

            if result.status == "success":
                self._tool_calls_succeeded += 1
                self._add_log("TOOL_SUCCESS", {"tool": tool_call.tool_name})
            else:
                self._tool_calls_failed += 1
                self._add_log("TOOL_FAILED", {
                    "tool": tool_call.tool_name,
                    "status": result.status,
                    "error": result.error,
                })

        return results

    def _should_complete(self) -> bool:
        """
        Check if agent has claimed completion.

        Look for completion markers in the last response.
        """
        if not self._conversation_history:
            return False

        last_msg = self._conversation_history[-1]
        content = last_msg.content.lower()

        # Look for completion markers
        completion_markers = [
            "task is complete",
            "complete",
            "done",
            "finished",
            "successfully completed",
            "all done",
        ]

        for marker in completion_markers:
            if marker in content:
                self._add_log("COMPLETION_CLAIM", {"marker": marker})
                return True

        return False

    def _build_context(self) -> str:
        """Build context string for LLM from task and workspace."""
        lines = [
            f"Task: {self._context.task.title}",
            f"Description: {self._context.task.description}",
            f"Workspace: {self._context.workspace_root}",
            "",
            "Acceptance Criteria:",
        ]

        for criterion in self._context.task.acceptance_criteria:
            lines.append(f"  - {criterion}")

        if self._context.task.allowed_paths:
            lines.append("")
            lines.append("Allowed Paths (restrict changes to these):")
            for path in self._context.task.allowed_paths:
                lines.append(f"  - {path}")

        lines.append("")
        lines.append("Available Tools:")
        for name, tool_def in self.tools_registry.items():
            lines.append(f"  - {name}: {tool_def.description}")

        return "\n".join(lines)

    def _build_result(self) -> AgentResult:
        """Build final result from execution."""
        duration_ms = (time.time() - self._start_time) * 1000 if self._start_time else 0

        status = "failed"
        if self.current_state == AgentState.VERIFYING:
            status = "success"  # Agent claimed completion, now verified by orchestrator
        elif self.current_state in [AgentState.COMPLETED]:
            status = "success"
        elif self.current_state == AgentState.CANCELLED:
            status = "cancelled"
        elif self.current_state == AgentState.TIMEOUT:
            status = "timeout"
        elif self.current_state == AgentState.BUDGET_EXCEEDED:
            status = "blocked"

        return AgentResult(
            run_id=self._context.run_id,
            agent_id=self.agent_id,
            task_id=self._context.task.task_id,
            attempt_id=self._context.attempt_id,
            status=status,
            final_state=self.current_state,
            summary=self._get_summary(),
            files_changed=self._extract_files_changed(),
            tool_calls_total=self._tool_calls_total,
            tool_calls_succeeded=self._tool_calls_succeeded,
            tool_calls_failed=self._tool_calls_failed,
            llm_calls=self._llm_calls,
            tokens_used=self._tokens_used,
            duration_ms=duration_ms,
        )

    def _get_summary(self) -> str:
        """Extract summary from agent's final response."""
        if not self._conversation_history:
            return "No execution"

        # Get last assistant message
        for msg in reversed(self._conversation_history):
            if msg.role == "assistant":
                return msg.content[:500]

        return "Completed"

    def _extract_files_changed(self) -> List[str]:
        """Extract file changes from tool call log."""
        files = set()
        for log in self._execution_log:
            if log.get("type") == "TOOL_CALL":
                # Could parse actual file modifications from git diff here
                pass
        return list(files)

    def _add_log(self, log_type: str, data: Dict[str, Any]) -> None:
        """Add entry to execution log."""
        self._execution_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "type": log_type,
                "state": str(self.current_state),
                "data": data,
            }
        )
