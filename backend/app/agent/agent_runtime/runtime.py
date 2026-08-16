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
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    COMPLETED = "COMPLETED"
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"

    # Backward compatibility alias
    INTERRUPTED = "FAILED"


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
        AgentState.EMPTY_RESPONSE,
        AgentState.COMPLETED,
        AgentState.COMPLETED_VERIFIED,
        AgentState.COMPLETED_WITH_WARNINGS,
    },
    AgentState.WAITING_FOR_TOOL: {AgentState.EXECUTING, AgentState.FAILED, AgentState.CANCELLED, AgentState.BLOCKED, AgentState.VERIFYING},
    AgentState.VERIFYING: {
        AgentState.VERIFYING,
        AgentState.EXECUTING,
        AgentState.WAITING_FOR_TOOL,
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
    AgentState.BLOCKED: {
        AgentState.IDLE,
        AgentState.PLANNING,
        AgentState.EXECUTING,
        AgentState.CANCELLED,
        AgentState.FAILED,
    },
    AgentState.EMPTY_RESPONSE: {AgentState.IDLE, AgentState.PLANNING, AgentState.EXECUTING},
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

    async def transition_state(
        self,
        session: AgentSessionState,
        new_state: AgentState,
        event_callback: Optional[Callable[[AgentEvent], None]] = None,
    ) -> None:
        """Enforce explicit state machine transition rules."""
        curr = session.state
        if new_state not in VALID_TRANSITIONS.get(curr, set()):
            if new_state == AgentState.CANCELLED:
                pass
            else:
                raise InvalidStateTransitionError(
                    f"Invalid AgentState transition: {curr.value} -> {new_state.value}"
                )

        session.state = new_state
        logger.info(f"Session {session.session_id} state transition: {curr.value} -> {new_state.value}")

        try:
            from backend.app.infrastructure.observability.telemetry import TelemetryManager
            tracer = TelemetryManager.get_tracer()
            with tracer.start_as_current_span(
                "agent.state_transition",
                attributes={
                    "from_state": curr.value,
                    "to_state": new_state.value if isinstance(new_state, AgentState) else str(new_state),
                    "session_id": session.session_id,
                },
            ):
                pass
        except Exception:
            pass

        from backend.app.infrastructure.database.connection import async_session_factory
        from backend.app.infrastructure.database.models import AgentRun
        from sqlalchemy import update
        try:
            async with async_session_factory() as db:
                await db.execute(
                    update(AgentRun)
                    .where(AgentRun.id == session.session_id)
                    .values(state=new_state.value if isinstance(new_state, AgentState) else str(new_state))
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Non-fatal: Failed to update AgentRun state in database for session {session.session_id}: {e}")

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
            if asyncio.iscoroutinefunction(event_callback):
                await event_callback(ev)
            else:
                event_callback(ev)

    async def save_checkpoint(self, session: AgentSessionState, checkpoint_type: str) -> None:
        from backend.app.infrastructure.database.connection import async_session_factory
        from backend.app.infrastructure.database.models import AgentCheckpoint
        import json
        
        state_data = {
            "current_step": session.current_step,
            "state": session.state.value if isinstance(session.state, AgentState) else str(session.state),
            "active_task_id": session.active_task_id,
            "verification_status": session.verification_status.value if isinstance(session.verification_status, VerificationStatus) else str(session.verification_status),
            "changed_files": session.changed_files,
            "errors": session.errors,
            "tool_calls_count": len(session.tool_calls),
            "started_at": session.started_at,
        }
        
        try:
            async with async_session_factory() as db:
                checkpoint = AgentCheckpoint(
                    run_id=session.session_id,
                    checkpoint_name=checkpoint_type,
                    state_json=json.dumps(state_data)
                )
                db.add(checkpoint)
                await db.commit()
                logger.info(f"Saved runtime checkpoint '{checkpoint_type}' for run {session.session_id}")
        except Exception as e:
            logger.warning(f"Non-fatal: Failed to save runtime checkpoint for session {session.session_id}: {e}")

    async def load_checkpoint(self, session: AgentSessionState, task_id: Optional[str] = None) -> bool:
        from backend.app.infrastructure.database.connection import async_session_factory
        from backend.app.infrastructure.database.models import AgentCheckpoint
        from sqlalchemy import select
        import json
        
        try:
            async with async_session_factory() as db:
                stmt = (
                    select(AgentCheckpoint)
                    .where(AgentCheckpoint.run_id == session.session_id)
                    .order_by(AgentCheckpoint.created_at.desc())
                )
                res = await db.execute(stmt)
                cp = res.scalars().first()
                if not cp:
                    return False
                    
                data = json.loads(cp.state_json)
                cp_task_id = data.get("active_task_id")
                # Do not resume checkpoint if task ID has changed
                if task_id and cp_task_id and cp_task_id != task_id:
                    return False

                cp_state = data.get("state", "IDLE")
                # Do not resume completed or terminal checkpoints
                if cp_state in ("COMPLETED", "COMPLETED_VERIFIED", "COMPLETED_WITH_WARNINGS", "FAILED", "CANCELLED"):
                    return False

                session.current_step = data.get("current_step", 0)
                session.state = AgentState(cp_state)
                session.active_task_id = cp_task_id
                session.verification_status = VerificationStatus(data.get("verification_status", "NOT_RUN"))
                session.changed_files = data.get("changed_files", {})
                session.errors = data.get("errors", [])
                session.started_at = data.get("started_at")
                logger.info(f"Successfully loaded checkpoint '{cp.checkpoint_name}' for run {session.session_id}. Resuming at step {session.current_step}.")
                return True
        except Exception as e:
            logger.warning(f"Non-fatal: Could not load runtime checkpoint (starting fresh): {e}")
            return False

    async def _finalize_run(
        self,
        session: AgentSessionState,
        state: AgentState,
        output: str,
        task_obj: AgentTask,
        tx_workspace: Optional[TransactionalWorkspace] = None,
        events_collected: Optional[List[AgentEvent]] = None,
        errors: Optional[List[str]] = None,
        emit_fn: Optional[Callable[[AgentEvent], None]] = None,
    ) -> AgentResult:
        """Centralized helper that sets state, persists checkpoint, and builds the final AgentResult.
        Guarantees consistent state transitions, single terminal state, and no duplicate error events.
        """
        if errors:
            for err in errors:
                if err and err not in session.errors:
                    session.errors.append(err)

        if session.state != state:
            try:
                if emit_fn:
                    await self.transition_state(session, state, emit_fn)
                else:
                    session.state = state
            except InvalidStateTransitionError:
                session.state = state

        session.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if tx_workspace and hasattr(tx_workspace, "change_set"):
            session.changed_files = tx_workspace.change_set.to_dict()
        elif not session.changed_files:
            session.changed_files = {}

        try:
            await self.save_checkpoint(session, f"final_{session.state.value if isinstance(session.state, AgentState) else str(session.state)}")
        except Exception as cp_err:
            logger.warning(f"Failed to save final checkpoint for session {session.session_id}: {cp_err}")

        return AgentResult(
            session_id=session.session_id,
            task_id=task_obj.id if task_obj else session.active_task_id or "",
            success=session.state in (AgentState.COMPLETED, AgentState.COMPLETED_VERIFIED, AgentState.COMPLETED_WITH_WARNINGS),
            state=session.state,
            output=output.strip() if output else "",
            changed_files=session.changed_files,
            verification_status=session.verification_status,
            errors=session.errors,
            events=events_collected or [],
        )

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
        conversation_messages: Optional[List[Dict[str, Any]]] = None,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentResult:
        """
        Execute a canonical agent coding session.
        llm_provider_func signature: async (messages: list, tools: list) -> ModelResponse
        It must be provided. Missing provider raises RuntimeError immediately.
        """
        if session_id not in self._sessions:
            await self.start_session(self.workspace_root, session_id=session_id)

        session = self._sessions[session_id]
        cancel_event = self._cancellation_events.setdefault(session_id, asyncio.Event())
        cancel_event.clear()
        try:
            from backend.app.state import clear_run_cancelled, is_run_cancelled
            await clear_run_cancelled(session_id)
        except Exception:
            pass

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

        has_checkpoint = await self.load_checkpoint(session, task_id=task_obj.id)

        if not has_checkpoint:
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

        agent_context = None
        if not has_checkpoint:
            _emit(AgentEvent(session_id, EVENT_AGENT_STARTED, {"task_id": task_obj.id, "description": task_obj.description}))

            # Build canonical repository context via ContextEngine
            from backend.app.agent.context_engine import ContextEngine, WorkspaceContext
            ctx_engine = ContextEngine.get_instance(session.workspace_root)
            agent_context = await ctx_engine.build_context(
                task_description=task_obj.description,
                workspace=WorkspaceContext(workspace_root=session.workspace_root),
            )

            # 1. State transition -> PLANNING
            await self.transition_state(session, AgentState.PLANNING, _emit)
            _emit(AgentEvent(session_id, EVENT_AGENT_PLAN_CREATED, {
                "task": task_obj.description,
                "plan": "Analyzing workspace and context.",
                "tokens_estimate": agent_context.total_tokens_estimate,
                "context_files": [item.file for item in agent_context.items],
            }))

            # 2. State transition -> EXECUTING
            await self.transition_state(session, AgentState.EXECUTING, _emit)

        # Initialize mutable conversation message list for multi-turn LLM dialogue
        context_block = ""
        try:
            ctx_parts: list[str] = []
            if agent_context and hasattr(agent_context, "items"):
                for item in agent_context.items:
                    header = f"### {item.file}"
                    if item.line_start and item.line_end:
                        header += f" (lines {item.line_start}-{item.line_end})"
                    ctx_parts.append(f"{header}\n```\n{item.content}\n```")
            if ctx_parts:
                context_block = (
                    "\n\n<workspace_context>\n"
                    + "\n\n".join(ctx_parts)
                    + "\n</workspace_context>\n\n"
                )
            elif session.workspace_root and os.path.isdir(session.workspace_root):
                # Fallback: plain directory listing when context engine finds nothing
                entries: list[str] = []
                for root_dir, dirs, files in os.walk(session.workspace_root):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
                    rel = os.path.relpath(root_dir, session.workspace_root)
                    for f in files:
                        entries.append(os.path.join(rel, f) if rel != "." else f)
                    if len(entries) > 200:
                        break
                if entries:
                    context_block = (
                        "\n\n<workspace_context>\n### Workspace file listing\n"
                        + "\n".join(f"- {e}" for e in entries[:200])
                        + "\n</workspace_context>\n\n"
                    )
        except Exception as ctx_err:
            logger.warning(f"Failed to build context block: {ctx_err}")

        if conversation_messages is None:
            conversation_messages = [
                {"role": "user", "content": context_block + task_obj.description}
            ]
        else:
            conversation_messages = list(conversation_messages)
            if conversation_messages and conversation_messages[-1].get("role") == "user":
                last_content = conversation_messages[-1].get("content", "")
                if "<workspace_context>" not in last_content and context_block:
                    conversation_messages[-1] = {
                        **conversation_messages[-1],
                        "content": context_block + last_content
                    }

        # Build tool schemas list from ToolRegistry if not provided
        if tool_schemas is None:
            from backend.app.infrastructure.tool_registry import ToolRegistry
            tool_schemas = [
                {
                    "name": td.name,
                    "description": td.description,
                    "input_schema": (
                        td.input_schema.model_json_schema() if hasattr(td.input_schema, "model_json_schema")
                        else (td.input_schema.schema() if hasattr(td.input_schema, "schema") else {})
                    ),
                }
                for td in ToolRegistry.get_all_tools()
            ]

        tool_executor = ToolExecutor(session.workspace_root, session=agent_session)
        tx_workspace = TransactionalWorkspace(session.workspace_root)

        step = session.current_step if has_checkpoint else 0
        final_output = ""

        try:
            while step < max_turns:
                step += 1
                session.current_step = step

                if cancel_event.is_set() or await self._is_cancelled(session_id):
                    if not cancel_event.is_set():
                        cancel_event.set()
                    _emit(AgentEvent(session_id, EVENT_AGENT_CANCELLED, {"step": step}))
                    return await self._finalize_run(
                        session=session,
                        state=AgentState.CANCELLED,
                        output="Execution cancelled by user.",
                        task_obj=task_obj,
                        tx_workspace=tx_workspace,
                        events_collected=events_collected,
                        errors=["Task cancelled"],
                        emit_fn=_emit,
                    )

                # LLM Generation Step
                model_resp: ModelResponse
                if not llm_provider_func:
                    raise RuntimeError(
                        "AgentRuntime requires a configured LLM provider. "
                        "Pass llm_provider_func to runtime.run()."
                    )

                import os as _os
                _llm_turn_timeout = float(
                    _os.environ.get("DEVPILOT_LLM_TURN_TIMEOUT") or "600.0"
                )
                raw_res = await asyncio.wait_for(
                    llm_provider_func(list(conversation_messages), list(tool_schemas)),
                    timeout=_llm_turn_timeout,
                )
                model_resp = ModelResponseNormalizer.normalize_response(raw_res)

                # Assert LLM did not return an empty response with no tool calls
                if not (model_resp.text or "").strip() and not model_resp.tool_calls:
                    logger.warning("LLM turn produced no text content and no tool calls. Transitioning to EMPTY_RESPONSE.")
                    session.errors.append("Model provider returned empty response.")
                    return await self._finalize_run(
                        session=session,
                        state=AgentState.EMPTY_RESPONSE,
                        output=final_output.strip(),
                        task_obj=task_obj,
                        tx_workspace=tx_workspace,
                        events_collected=events_collected,
                        emit_fn=_emit,
                    )

                # Append assistant message to conversation history for next turn
                asst_msg: Dict[str, Any] = {"role": "assistant", "content": model_resp.text or ""}
                if model_resp.tool_calls:
                    asst_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                            "thought_signature": getattr(tc, "thought_signature", None),
                        }
                        for tc in model_resp.tool_calls
                    ]
                conversation_messages.append(asst_msg)

                # Persist assistant message to session history if active
                if agent_session is not None:
                    session_asst_msg = {
                        "role": "assistant",
                        "content": model_resp.text or "",
                    }
                    if model_resp.tool_calls:
                        session_asst_msg["tool_calls"] = [
                            {
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                                "thought_signature": getattr(tc, "thought_signature", None),
                            }
                            for tc in model_resp.tool_calls
                        ]
                    agent_session.conversation_history.append(session_asst_msg)

                if model_resp.text:
                    final_output += model_resp.text + "\n"

                if not model_resp.tool_calls:
                    # No tool calls: LLM finished reasoning turn
                    break

                # Process Tool Calls
                for tc in model_resp.tool_calls:
                    if cancel_event.is_set() or await self._is_cancelled(session_id):
                        if not cancel_event.is_set():
                            cancel_event.set()
                        break

                    await self.transition_state(session, AgentState.WAITING_FOR_TOOL, _emit)
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

                    # Append tool result to conversation history for next LLM turn
                    tool_result_content = str(tool_res.output) if tool_res.success else (tool_res.error or "Tool execution failed")
                    conversation_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_result_content[:8192],  # truncate large outputs
                    })

                    await self.transition_state(session, AgentState.EXECUTING, _emit)
                    await self.save_checkpoint(session, f"after_tool_{tc.name}")

            if session.state == AgentState.CANCELLED or cancel_event.is_set():
                _emit(AgentEvent(session_id, EVENT_AGENT_CANCELLED, {"step": step if 'step' in locals() else 0}))
                return await self._finalize_run(
                    session=session,
                    state=AgentState.CANCELLED,
                    output="Execution cancelled by user.",
                    task_obj=task_obj,
                    tx_workspace=tx_workspace,
                    events_collected=events_collected,
                    errors=["Task cancelled"],
                    emit_fn=_emit,
                )

            # 3. State transition -> VERIFYING & AUTONOMOUS SELF-REPAIR
            await self.transition_state(session, AgentState.VERIFYING, _emit)
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
            _loop_blocked = False  # Track if BLOCKED state was entered to exit outer loop
            for phase, cmd in PHASE_COMMANDS.items():
                if _loop_blocked:
                    break
                phase_state["current_phase"] = phase
                phase_state["active_phase"] = phase
                phase_state["next_action"] = f"run_{phase.lower().replace(' ', '_')}"
                v_engine.save_phase_state(phase_state)

                # Execute the check — only transition to VERIFYING if not already BLOCKED
                if session.state != AgentState.BLOCKED:
                    await self.transition_state(session, AgentState.VERIFYING, _emit)
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
                        await self.transition_state(session, AgentState.BLOCKED, _emit)
                        session.errors.append("Repeated failure loop detected in self-repair.")
                        all_phases_passed = False
                        _loop_blocked = True
                        break

                    await self.transition_state(session, AgentState.REPAIRING, _emit)

                    # Build repair prompt and invoke LLM to produce actual repair tool calls
                    repair_prompt = (
                        f"The {phase} check failed. Error output:\n{v_res.output[:2000]}\n\n"
                        f"Please analyze the failure and use the available tools to fix the issue."
                    )
                    repair_messages = list(conversation_messages) + [
                        {"role": "user", "content": repair_prompt}
                    ]

                    try:
                        import os as _os
                        _repair_timeout = float(_os.environ.get("DEVPILOT_LLM_TURN_TIMEOUT") or "600.0")
                        raw_repair_res = await asyncio.wait_for(
                            llm_provider_func(repair_messages, list(tool_schemas)),
                            timeout=_repair_timeout,
                        )
                        repair_model_resp = ModelResponseNormalizer.normalize_response(raw_repair_res)

                        # Append assistant repair message to history
                        repair_asst_msg: Dict[str, Any] = {"role": "assistant", "content": repair_model_resp.text or ""}
                        if repair_model_resp.tool_calls:
                            repair_asst_msg["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                                }
                                for tc in repair_model_resp.tool_calls
                            ]
                        conversation_messages.append(repair_asst_msg)

                        # Execute any repair tool calls from LLM
                        for r_tc in repair_model_resp.tool_calls:
                            _emit(AgentEvent(session_id, EVENT_TOOL_STARTED, {"tool_call_id": r_tc.id, "name": r_tc.name, "arguments": r_tc.arguments}))
                            r_target_file = r_tc.arguments.get("path") or r_tc.arguments.get("TargetFile") or r_tc.arguments.get("file_path")
                            r_pre_snap = None
                            if r_target_file and r_tc.name in ("write_file", "edit_file", "delete_file", "apply_patch"):
                                r_pre_snap = tx_workspace.capture_pre_state(r_target_file)

                            r_tool_res = await tool_executor.execute(
                                tool_call_id=r_tc.id,
                                tool_name=r_tc.name,
                                arguments=r_tc.arguments,
                                timeout=60.0,
                                auto_apply=task_obj.auto_apply,
                            )

                            _emit(AgentEvent(session_id, EVENT_TOOL_COMPLETED, {"tool_call_id": r_tc.id, "name": r_tc.name, "success": r_tool_res.success, "error": r_tool_res.error}))

                            if r_target_file and r_tc.name in ("write_file", "edit_file", "delete_file", "apply_patch"):
                                r_diff = tx_workspace.capture_post_state(r_target_file, r_pre_snap)
                                if r_diff:
                                    _emit(AgentEvent(session_id, EVENT_FILE_CHANGED, {"file": r_target_file, "diff": r_diff}))

                            r_tool_content = str(r_tool_res.output) if r_tool_res.success else (r_tool_res.error or "Tool execution failed")
                            conversation_messages.append({
                                "role": "tool",
                                "tool_call_id": r_tc.id,
                                "name": r_tc.name,
                                "content": r_tool_content[:8192],
                            })

                        repair_loop.record_repair_attempt(failure, repair_model_resp.text or "LLM repair turn", len(repair_model_resp.tool_calls) > 0)
                    except Exception as repair_err:
                        logger.error(f"Repair LLM call failed: {repair_err}")
                        repair_loop.record_repair_attempt(failure, f"Repair failed: {repair_err}", False)

                    # Re-run phase verification — only if not blocked
                    if not _loop_blocked:
                        if session.state != AgentState.BLOCKED:
                            await self.transition_state(session, AgentState.VERIFYING, _emit)
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
            await self.save_checkpoint(session, "after_verification")

            # 3b. Dual-LLM critic debate on the accumulated change set
            try:
                from backend.app.debate.debate_engine import debate_engine
                from backend.app.debate.consensus import consensus_engine

                diff_summary = json.dumps(tx_workspace.change_set.to_dict(), default=str)[:6000]
                critiques = await debate_engine.hold_debate(diff_summary)
                if critiques:
                    approved = consensus_engine.resolve_consensus(critiques)
                    _emit(AgentEvent(
                        session_id,
                        "agent.debate.completed",
                        {
                            "approved": approved,
                            "critiques": [
                                {
                                    "agent": c.agent_name,
                                    "score": c.score,
                                    "blocking": c.is_blocking,
                                    "feedback": c.feedback,
                                }
                                for c in critiques
                            ],
                        },
                    ))
                    if not approved:
                        low = min(critiques, key=lambda c: c.score)
                        session.errors.append(f"Debate rejected: {low.feedback}")
                        # Stay recoverable: VERIFYING -> REPAIRING is valid; final
                        # assignment below will mark FAILED if unrepaired.
                        if session.state == AgentState.VERIFYING:
                            await self.transition_state(session, AgentState.REPAIRING, _emit)
                        session.verification_status = VerificationStatus.FAILED
            except Exception as debate_err:
                logger.warning(f"DebateEngine skipped due to error: {debate_err}")

            # 4. Acceptance Criteria & Agent Reviewer
            changed_files_list = list(tx_workspace.change_set.modified_files | tx_workspace.change_set.created_files)
            review_res = AgentReviewer.review_task(contract, changed_files_list, v_res)
            _emit(AgentEvent(session_id, "agent.review.completed", {"review": review_res.to_dict()}))

            # 5. Final State Assignment
            if session.state == AgentState.BLOCKED:
                target_state = AgentState.BLOCKED
            elif session.verification_status == VerificationStatus.PASSED and review_res.approved:
                target_state = AgentState.COMPLETED_VERIFIED
                _emit(AgentEvent(session_id, EVENT_AGENT_COMPLETED, {"output": final_output.strip(), "verified": True}))
            elif session.verification_status == VerificationStatus.PASSED:
                target_state = AgentState.COMPLETED_WITH_WARNINGS
                _emit(AgentEvent(session_id, EVENT_AGENT_COMPLETED, {"output": final_output.strip(), "verified": False}))
            else:
                target_state = AgentState.FAILED

            return await self._finalize_run(
                session=session,
                state=target_state,
                output=final_output,
                task_obj=task_obj,
                tx_workspace=tx_workspace,
                events_collected=events_collected,
                emit_fn=_emit,
            )

        except Exception as e:
            if session.state == AgentState.CANCELLED or cancel_event.is_set():
                _emit(AgentEvent(session_id, EVENT_AGENT_CANCELLED, {"step": step if 'step' in locals() else 0}))
                return await self._finalize_run(
                    session=session,
                    state=AgentState.CANCELLED,
                    output="Execution cancelled by user.",
                    task_obj=task_obj,
                    tx_workspace=tx_workspace,
                    events_collected=events_collected,
                    errors=["Task cancelled"],
                    emit_fn=_emit,
                )

            logger.exception(f"AgentRuntime session {session_id} failed with exception: {e}")
            return await self._finalize_run(
                session=session,
                state=AgentState.FAILED,
                output=final_output,
                task_obj=task_obj,
                tx_workspace=tx_workspace,
                events_collected=events_collected,
                errors=[str(e)],
                emit_fn=_emit,
            )

    async def _is_cancelled(self, session_id: str) -> bool:
        """Check in-process cancel event plus Redis cancel flag (multi-worker safe)."""
        local = self._cancellation_events.get(session_id)
        if local and local.is_set():
            return True
        try:
            from backend.app.state import is_run_cancelled
            return await is_run_cancelled(session_id)
        except Exception:
            return False

    async def cancel(self, session_id: str) -> None:
        """Cancel an active agent session (Step 11 requirement)."""
        if session_id in self._cancellation_events:
            self._cancellation_events[session_id].set()

        try:
            from backend.app.state import set_run_cancelled
            await set_run_cancelled(session_id)
        except Exception as e:
            logger.warning(f"Failed to persist cancel flag for {session_id}: {e}")

        # Stop active process supervisor / global processes on cancellation
        try:
            from backend.app.processes import global_process_manager
            procs = global_process_manager.get_running_processes()
            for p in procs:
                asyncio.create_task(p.stop())
        except Exception as e:
            logger.warning(f"Error terminating processes on session cancellation: {e}")

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
