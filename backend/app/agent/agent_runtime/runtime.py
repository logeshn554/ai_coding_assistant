"""
Unified Agent Runtime — Canonical execution engine for all AI coding operations.

Implements the single AgentRuntime interface, explicit state machine, event generation,
normalized tool execution, transactional file tracking, cancellation, and verification.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
from enum import Enum
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .events import (
    AgentEvent,
    EVENT_AGENT_CANCELLED,
    EVENT_AGENT_COMPLETED,
    EVENT_AGENT_ERROR,
    EVENT_AGENT_PLAN_CREATED,
    EVENT_AGENT_STARTED,
    EVENT_AGENT_STATE_CHANGED,
    EVENT_COMMAND_COMPLETED,
    EVENT_COMMAND_OUTPUT,
    EVENT_COMMAND_STARTED,
    EVENT_FILE_CHANGED,
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_STARTED,
    EVENT_VERIFICATION_COMPLETED,
    EVENT_VERIFICATION_STARTED,
)
from .llm_adapter import ModelResponse, ModelResponseNormalizer, ToolCall
from .tool_executor import ToolExecutor, ToolResult
from .transactional_workspace import TransactionalWorkspace

logger = logging.getLogger("devpilot.agent_runtime")


class AgentState(str, Enum):
    """Explicit agent session states."""
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"


class VerificationStatus(str, Enum):
    """Verification interface statuses."""
    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


# Allowed state transitions
VALID_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
    AgentState.IDLE: {AgentState.PLANNING, AgentState.EXECUTING, AgentState.CANCELLED},
    AgentState.PLANNING: {AgentState.EXECUTING, AgentState.FAILED, AgentState.CANCELLED, AgentState.WAITING_FOR_APPROVAL},
    AgentState.EXECUTING: {
        AgentState.WAITING_FOR_TOOL,
        AgentState.VERIFYING,
        AgentState.REPAIRING,
        AgentState.WAITING_FOR_APPROVAL,
        AgentState.FAILED,
        AgentState.CANCELLED,
        AgentState.BLOCKED,
        AgentState.COMPLETED,
        AgentState.COMPLETED_VERIFIED,
        AgentState.COMPLETED_WITH_WARNINGS,
    },
    AgentState.WAITING_FOR_TOOL: {AgentState.EXECUTING, AgentState.FAILED, AgentState.CANCELLED, AgentState.BLOCKED},
    AgentState.VERIFYING: {
        AgentState.VERIFYING,
        AgentState.COMPLETED,
        AgentState.COMPLETED_VERIFIED,
        AgentState.COMPLETED_WITH_WARNINGS,
        AgentState.REPAIRING,
        AgentState.FAILED,
        AgentState.CANCELLED,
        AgentState.BLOCKED,
    },
    AgentState.REPAIRING: {
        AgentState.REPAIRING,
        AgentState.VERIFYING,
        AgentState.EXECUTING,
        AgentState.FAILED,
        AgentState.CANCELLED,
        AgentState.BLOCKED,
    },
    AgentState.WAITING_FOR_APPROVAL: {
        AgentState.EXECUTING,
        AgentState.PLANNING,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.FAILED: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING, AgentState.CANCELLED},
    AgentState.CANCELLED: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING},
    AgentState.BLOCKED: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING, AgentState.CANCELLED},
    AgentState.COMPLETED: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING},
    AgentState.COMPLETED_VERIFIED: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING},
    AgentState.COMPLETED_WITH_WARNINGS: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING},
}


@dataclass
class AgentTask:
    """Task specification passed to the AgentRuntime."""
    id: str
    description: str
    mode: str = "Agent"
    auto_apply: bool = False
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSessionState:
    """Strongly typed session state container."""
    session_id: str
    workspace_root: str
    profile: Dict[str, Any] = field(default_factory=dict)
    state: AgentState = AgentState.IDLE
    current_step: int = 0
    active_task_id: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    changed_files: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "workspace_root": self.workspace_root,
            "state": self.state.value if isinstance(self.state, AgentState) else str(self.state),
            "current_step": self.current_step,
            "active_task_id": self.active_task_id,
            "tool_calls_count": len(self.tool_calls),
            "changed_files": self.changed_files,
            "errors": self.errors,
            "verification_status": self.verification_status.value if isinstance(self.verification_status, VerificationStatus) else str(self.verification_status),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class AgentResult:
    """Final result returned by AgentRuntime.run()."""
    session_id: str
    task_id: str
    success: bool
    state: AgentState
    output: str
    changed_files: Dict[str, Any] = field(default_factory=dict)
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN
    errors: List[str] = field(default_factory=list)
    events: List[AgentEvent] = field(default_factory=list)


class AgentRuntime:
    """The canonical AgentRuntime orchestrating model calls, tool execution, state machine, and events."""

    _sessions: Dict[str, AgentSessionState] = {}
    _active_tasks: Dict[str, asyncio.Task] = {}
    _cancellation_events: Dict[str, asyncio.Event] = {}

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or os.getcwd()

    async def start_session(
        self,
        workspace_root: str,
        profile: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> AgentSessionState:
        """Initialize or retrieve a canonical AgentSessionState."""
        sid = session_id or f"session_{int(time.time()*1000)}"
        root = workspace_root or self.workspace_root
        
        session = AgentSessionState(
            session_id=sid,
            workspace_root=root,
            profile=profile or {},
            state=AgentState.IDLE,
        )
        self._sessions[sid] = session
        self._cancellation_events[sid] = asyncio.Event()
        logger.info(f"AgentRuntime session started: {sid}")
        return session

    def transition_state(
        self,
        session: AgentSessionState,
        new_state: AgentState,
        event_callback: Optional[Callable[[AgentEvent], None]] = None,
    ) -> None:
        """Enforce explicit state machine transition rules."""
        curr = session.state
        if new_state not in VALID_TRANSITIONS.get(curr, set()):
            # Special bypass for emergency cancellation from any active state
            if new_state == AgentState.CANCELLED:
                pass
            else:
                raise InvalidStateTransitionError(
                    f"Invalid AgentState transition: {curr.value} -> {new_state.value}"
                )

        session.state = new_state
        logger.info(f"Session {session.session_id} state transition: {curr.value} -> {new_state.value}")

        ev = AgentEvent(
            session_id=session.session_id,
            type=EVENT_AGENT_STATE_CHANGED,
            payload={
                "previous_state": curr.value,
                "current_state": new_state.value,
                "step": session.current_step,
            },
        )
        if event_callback:
            event_callback(ev)

    async def run(
        self,
        session_id: str,
        task: str | AgentTask,
        mode: str = "Agent",
        auto_apply: bool = False,
        event_callback: Optional[Callable[[AgentEvent], Any]] = None,
        max_turns: int = 25,
        llm_provider_func: Optional[Callable] = None,
        agent_session: Optional[Any] = None,  # added actual AgentSession reference
    ) -> AgentResult:
        """Execute a canonical agent coding session."""
        if session_id not in self._sessions:
            await self.start_session(self.workspace_root, session_id=session_id)

        session = self._sessions[session_id]
        cancel_event = self._cancellation_events.setdefault(session_id, asyncio.Event())
        cancel_event.clear()

        task_obj: AgentTask
        if isinstance(task, str):
            import uuid
            task_obj = AgentTask(
                id=f"task_{uuid.uuid4().hex[:8]}",
                description=task,
                mode=mode,
                auto_apply=auto_apply,
            )
        else:
            task_obj = task

        session.active_task_id = task_obj.id
        session.started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        session.errors.clear()
        session.tool_calls.clear()

        events_collected: List[AgentEvent] = []

        def _emit(event: AgentEvent):
            events_collected.append(event)
            if event_callback:
                try:
                    if asyncio.iscoroutinefunction(event_callback):
                        asyncio.create_task(event_callback(event))
                    else:
                        event_callback(event)
                except Exception as ex:
                    logger.warning(f"Event callback error: {ex}")

        _emit(AgentEvent(session_id, EVENT_AGENT_STARTED, {"task_id": task_obj.id, "description": task_obj.description}))

        # Build canonical repository context via ContextEngine
        from backend.app.agent.context_engine import ContextEngine, WorkspaceContext
        ctx_engine = ContextEngine.get_instance(session.workspace_root)
        agent_context = await ctx_engine.build_context(
            task_description=task_obj.description,
            workspace=WorkspaceContext(workspace_root=session.workspace_root),
        )

        # 1. State transition -> PLANNING
        self.transition_state(session, AgentState.PLANNING, _emit)
        _emit(AgentEvent(session_id, EVENT_AGENT_PLAN_CREATED, {
            "task": task_obj.description,
            "plan": "Analyzing workspace and context.",
            "tokens_estimate": agent_context.total_tokens_estimate,
            "context_files": [item.file for item in agent_context.items],
        }))

        tool_executor = ToolExecutor(session.workspace_root, session=agent_session)
        tx_workspace = TransactionalWorkspace(session.workspace_root)

        # 2. State transition -> EXECUTING
        self.transition_state(session, AgentState.EXECUTING, _emit)

        step = 0
        final_output = ""

        try:
            while step < max_turns:
                step += 1
                session.current_step = step

                if cancel_event.is_set():
                    self.transition_state(session, AgentState.CANCELLED, _emit)
                    _emit(AgentEvent(session_id, EVENT_AGENT_CANCELLED, {"step": step}))
                    return AgentResult(
                        session_id=session_id,
                        task_id=task_obj.id,
                        success=False,
                        state=AgentState.CANCELLED,
                        output="Execution cancelled by user.",
                        changed_files=tx_workspace.change_set.to_dict(),
                        verification_status=session.verification_status,
                        errors=["Task cancelled"],
                        events=events_collected,
                    )

                # LLM Generation Step
                model_resp: ModelResponse
                if llm_provider_func:
                    raw_res = await asyncio.wait_for(
                        llm_provider_func(task_obj.description, step),
                        timeout=120.0,
                    )
                    model_resp = ModelResponseNormalizer.normalize_response(raw_res)
                else:
                    # Fallback internal mock / default adapter response if none supplied
                    model_resp = ModelResponse(
                        text=f"Completed action step {step} for: {task_obj.description}",
                        tool_calls=[],
                        finish_reason="end_turn",
                    )

                if model_resp.text:
                    final_output += model_resp.text + "\n"

                if not model_resp.tool_calls:
                    # No tool calls: LLM finished reasoning turn
                    break

                # Process Tool Calls
                for tc in model_resp.tool_calls:
                    if cancel_event.is_set():
                        break

                    self.transition_state(session, AgentState.WAITING_FOR_TOOL, _emit)
                    _emit(AgentEvent(session_id, EVENT_TOOL_STARTED, {"tool_call_id": tc.id, "name": tc.name, "arguments": tc.arguments}))

                    # Capture pre-modification file snapshot if write/edit tool
                    target_file = tc.arguments.get("path") or tc.arguments.get("TargetFile") or tc.arguments.get("file_path")
                    pre_snap = None
                    if target_file and tc.name in ("write_file", "edit_file", "delete_file", "apply_patch"):
                        pre_snap = tx_workspace.capture_pre_state(target_file)

                    # Execute tool call
                    tool_res: ToolResult = await tool_executor.execute(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        timeout=60.0,
                        auto_apply=task_obj.auto_apply,
                    )

                    session.tool_calls.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "success": tool_res.success,
                    })

                    _emit(AgentEvent(session_id, EVENT_TOOL_COMPLETED, {
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "success": tool_res.success,
                        "output": tool_res.output if tool_res.success else None,
                        "error": tool_res.error,
                    }))

                    if agent_session is not None:
                        from backend.app.context_helpers import prepare_tool_result_for_history
                        compact_result = prepare_tool_result_for_history(
                            tool_res.output if tool_res.success else (tool_res.error or "Error executing tool"),
                            tool_name=tc.name
                        )

                        entry = {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tc.name,
                            "content": compact_result
                        }
                        if len(str(tool_res.output if tool_res.success else (tool_res.error or ""))) > len(compact_result):
                            entry["metadata"] = {
                                "truncated": True,
                                "original_chars": len(str(tool_res.output if tool_res.success else (tool_res.error or ""))),
                                "retained_chars": len(compact_result)
                            }
                        agent_session.conversation_history.append(entry)

                        await agent_session.send_ws_message({
                            "type": "tool_result",
                            "tool_call_id": tc.id,
                            "name": tc.name,
                            "status": "success" if tool_res.success else "error",
                            "result": tool_res.output if tool_res.success else tool_res.error
                        })

                    # Capture post-modification diff and update change set
                    if target_file and tc.name in ("write_file", "edit_file", "delete_file", "apply_patch"):
                        diff = tx_workspace.capture_post_state(target_file, pre_snap)
                        if diff:
                            _emit(AgentEvent(session_id, EVENT_FILE_CHANGED, {
                                "file": target_file,
                                "diff": diff,
                                "change_set": tx_workspace.change_set.to_dict(),
                            }))

                    if not tool_res.success:
                        session.errors.append(f"Tool {tc.name} failed: {tool_res.error}")

                    self.transition_state(session, AgentState.EXECUTING, _emit)

            if session.state == AgentState.CANCELLED or cancel_event.is_set():
                if session.state != AgentState.CANCELLED:
                    self.transition_state(session, AgentState.CANCELLED, _emit)
                _emit(AgentEvent(session_id, EVENT_AGENT_CANCELLED, {"step": step}))
                return AgentResult(
                    session_id=session_id,
                    task_id=task_obj.id,
                    success=False,
                    state=AgentState.CANCELLED,
                    output="Execution cancelled by user.",
                    changed_files=tx_workspace.change_set.to_dict(),
                    verification_status=session.verification_status,
                    errors=["Task cancelled"],
                    events=events_collected,
                )

            # 3. State transition -> VERIFYING & AUTONOMOUS SELF-REPAIR
            self.transition_state(session, AgentState.VERIFYING, _emit)
            session.verification_status = VerificationStatus.RUNNING
            _emit(AgentEvent(session_id, EVENT_VERIFICATION_STARTED, {"status": session.verification_status.value}))

            from backend.app.agent.autonomous import (
                AgentReviewer,
                ChangeSetValidator,
                ExecutionPlanner,
                FailureAnalyzer,
                SelfRepairLoop,
                TaskContractGenerator,
                VerificationEngine,
            )

            contract = TaskContractGenerator.create_contract(task_obj.description, session.workspace_root)
            _emit(AgentEvent(session_id, "agent.contract.created", {"contract": contract.to_dict()}))

            v_engine = VerificationEngine(session.workspace_root)
            repair_loop = SelfRepairLoop(contract)

            # Load persistent phase state
            phase_state = v_engine.load_phase_state()
            if "IMPLEMENTING" not in phase_state["completed_phases"]:
                phase_state["completed_phases"].append("IMPLEMENTING")
            
            # Keep track of the final verification result
            v_res = None
            
            # Sequential validation phases
            PHASE_COMMANDS = {
                "STATIC CHECK": v_engine.profile.lint_command,
                "TYPECHECK": v_engine.profile.typecheck_command,
                "TEST": v_engine.profile.test_command,
                "BUILD": v_engine.profile.build_command,
                "RUN": None,
                "VERIFY": None
            }
            
            all_phases_passed = True
            for phase, cmd in PHASE_COMMANDS.items():
                phase_state["current_phase"] = phase
                phase_state["active_phase"] = phase
                phase_state["next_action"] = f"run_{phase.lower().replace(' ', '_')}"
                v_engine.save_phase_state(phase_state)
                
                # Execute the check
                self.transition_state(session, AgentState.VERIFYING, _emit)
                v_res = await v_engine.run_phase_command(cmd)
                
                while not v_res.success and repair_loop.can_attempt_repair():
                    # Record failure in state
                    if phase not in phase_state["failed_validations"]:
                        phase_state["failed_validations"].append(phase)
                    err_msg = f"{phase} failed: {v_res.output[:200]}"
                    if err_msg not in phase_state["blocking_errors"]:
                        phase_state["blocking_errors"].append(err_msg)
                    phase_state["next_action"] = f"repair_{phase.lower().replace(' ', '_')}"
                    v_engine.save_phase_state(phase_state)

                    failure = FailureAnalyzer.analyze_output(v_res.command, v_res.output)
                    _emit(AgentEvent(session_id, "agent.repair.started", {"round": repair_loop.current_round + 1, "failure": failure.to_dict()}))

                    if repair_loop.detect_failure_loop(failure):
                        _emit(AgentEvent(session_id, "agent.repair.loop_detected", {"failure": failure.to_dict()}))
                        self.transition_state(session, AgentState.BLOCKED, _emit)
                        session.errors.append("Repeated failure loop detected in self-repair.")
                        all_phases_passed = False
                        break

                    self.transition_state(session, AgentState.REPAIRING, _emit)
                    repair_loop.record_repair_attempt(failure, f"Attempted self-repair patch for {phase}", False)

                    # Re-run phase verification
                    self.transition_state(session, AgentState.VERIFYING, _emit)
                    v_res = await v_engine.run_phase_command(cmd)
                    
                if not v_res.success:
                    all_phases_passed = False
                    break
                else:
                    # Phase passed
                    if phase not in phase_state["completed_phases"]:
                        phase_state["completed_phases"].append(phase)
                    phase_state["last_successful_validation"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    # Clean errors for this phase if resolved
                    phase_state["blocking_errors"] = [e for e in phase_state["blocking_errors"] if not e.startswith(phase)]
                    v_engine.save_phase_state(phase_state)

            if all_phases_passed:
                session.verification_status = VerificationStatus.PASSED
                phase_state["current_phase"] = "COMPLETED"
                phase_state["active_phase"] = "COMPLETED"
                phase_state["next_action"] = "done"
                if "COMPLETED" not in phase_state["completed_phases"]:
                    phase_state["completed_phases"].append("COMPLETED")
                v_engine.save_phase_state(phase_state)
            else:
                session.verification_status = VerificationStatus.FAILED
                
            if v_res is None:
                from backend.app.agent.autonomous.verification_engine import VerificationResult
                v_res = VerificationResult(
                    success=all_phases_passed,
                    command="none",
                    output="No checks run.",
                    duration_seconds=0.0
                )

            _emit(AgentEvent(session_id, EVENT_VERIFICATION_COMPLETED, {"status": session.verification_status.value, "command": v_res.command}))

            # 4. Acceptance Criteria & Agent Reviewer
            changed_files_list = list(tx_workspace.change_set.modified_files | tx_workspace.change_set.created_files)
            review_res = AgentReviewer.review_task(contract, changed_files_list, v_res)
            _emit(AgentEvent(session_id, "agent.review.completed", {"review": review_res.to_dict()}))

            # 5. Final State Assignment
            if session.state == AgentState.BLOCKED:
                _emit(AgentEvent(session_id, EVENT_AGENT_ERROR, {"errors": session.errors}))
            elif session.verification_status == VerificationStatus.PASSED and review_res.approved:
                self.transition_state(session, AgentState.COMPLETED_VERIFIED, _emit)
                _emit(AgentEvent(session_id, EVENT_AGENT_COMPLETED, {"output": final_output.strip(), "verified": True}))
            elif session.verification_status == VerificationStatus.PASSED:
                self.transition_state(session, AgentState.COMPLETED_WITH_WARNINGS, _emit)
                _emit(AgentEvent(session_id, EVENT_AGENT_COMPLETED, {"output": final_output.strip(), "verified": False}))
            else:
                self.transition_state(session, AgentState.FAILED, _emit)
                _emit(AgentEvent(session_id, EVENT_AGENT_ERROR, {"errors": session.errors or ["Verification failed"]}))

            session.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            session.changed_files = tx_workspace.change_set.to_dict()

            return AgentResult(
                session_id=session_id,
                task_id=task_obj.id,
                success=session.state in (AgentState.COMPLETED, AgentState.COMPLETED_VERIFIED, AgentState.COMPLETED_WITH_WARNINGS),
                state=session.state,
                output=final_output.strip(),
                changed_files=session.changed_files,
                verification_status=session.verification_status,
                errors=session.errors,
                events=events_collected,
            )

        except Exception as e:
            if session.state == AgentState.CANCELLED or cancel_event.is_set():
                if session.state != AgentState.CANCELLED:
                    session.state = AgentState.CANCELLED
                _emit(AgentEvent(session_id, EVENT_AGENT_CANCELLED, {"step": step}))
                return AgentResult(
                    session_id=session_id,
                    task_id=task_obj.id,
                    success=False,
                    state=AgentState.CANCELLED,
                    output="Execution cancelled by user.",
                    changed_files=tx_workspace.change_set.to_dict(),
                    verification_status=session.verification_status,
                    errors=["Task cancelled"],
                    events=events_collected,
                )

            logger.exception(f"AgentRuntime session {session_id} failed with exception: {e}")
            session.errors.append(str(e))
            self.transition_state(session, AgentState.FAILED, _emit)
            _emit(AgentEvent(session_id, EVENT_AGENT_ERROR, {"error": str(e)}))
            return AgentResult(
                session_id=session_id,
                task_id=task_obj.id,
                success=False,
                state=AgentState.FAILED,
                output=final_output.strip(),
                changed_files=tx_workspace.change_set.to_dict(),
                verification_status=session.verification_status,
                errors=session.errors,
                events=events_collected,
            )

    async def cancel(self, session_id: str) -> None:
        """Cancel an active agent session (Step 11 requirement)."""
        if session_id in self._cancellation_events:
            self._cancellation_events[session_id].set()

        session = self._sessions.get(session_id)
        if session and session.state not in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED):
            session.state = AgentState.CANCELLED
            logger.info(f"AgentRuntime session {session_id} cancelled.")

    async def resume(self, session_id: str, task_description: Optional[str] = None) -> AgentResult:
        """Resume a session from persisted state (Step 3 & 15 requirement)."""
        session = self._sessions.get(session_id)
        if not session:
            session = await self.start_session(self.workspace_root, session_id=session_id)
        
        task_desc = task_description or "Resumed task session."
        return await self.run(session_id, task=task_desc)
