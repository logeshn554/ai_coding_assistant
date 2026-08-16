"""
Canonical Tool Executor — Step 5 requirement.

Single execution pipeline for all tools, producing structured ToolResult instances
and tracking audit history per tool execution.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("devpilot.agent_runtime.tool_executor")


@dataclass
class ToolResult:
    """Structured result returned by the ToolExecutor."""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionRecord:
    """Audit log entry for a tool execution."""
    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    start_time: str
    end_time: str
    duration_seconds: float
    success: bool
    output: Any
    error: Optional[str] = None


class _SessionBridge:
    """Bridge providing workspace_root and fallback callbacks to dispatch_tool."""

    def __init__(self, workspace_root: str, inner_session: Any = None):
        self.workspace_root = workspace_root
        self.inner_session = inner_session
        self.pending_confirmations = getattr(inner_session, "pending_confirmations", {})
        self.permission_manager = getattr(inner_session, "permission_manager", None)
        self.audit_log = getattr(inner_session, "audit_log", [])
        self.conversation_history = getattr(inner_session, "conversation_history", [])
        self.wasted_turns = getattr(inner_session, "wasted_turns", 0)

    async def send_ws_message(self, msg: dict):
        if self.inner_session and hasattr(self.inner_session, "send_ws_message"):
            try:
                res = self.inner_session.send_ws_message(msg)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Failed to forward message via _SessionBridge: {e}")

    def log_audit(self, *args, **kwargs):
        if self.inner_session and hasattr(self.inner_session, "log_audit"):
            try:
                self.inner_session.log_audit(*args, **kwargs)
            except Exception as e:
                logger.error(f"Failed to record audit log via _SessionBridge: {e}")
        else:
            self.audit_log.append({"args": args, "kwargs": kwargs})

    def __getattr__(self, name: str) -> Any:
        if self.inner_session and hasattr(self.inner_session, name):
            return getattr(self.inner_session, name)
        raise AttributeError(f"'_SessionBridge' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        if name in ("workspace_root", "inner_session", "pending_confirmations", "permission_manager", "audit_log", "conversation_history", "wasted_turns"):
            super().__setattr__(name, value)
        elif hasattr(self, "inner_session") and self.inner_session is not None:
            setattr(self.inner_session, name, value)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name: str):
        if hasattr(self, "inner_session") and self.inner_session is not None and hasattr(self.inner_session, name):
            delattr(self.inner_session, name)
        else:
            try:
                super().__delattr__(name)
            except AttributeError:
                pass


from backend.app.infrastructure.tool_registry import ToolRegistry

class ToolExecutor:
    """One canonical tool executor handling workspace and terminal tools."""

    def __init__(self, workspace_root: str, session: Any = None) -> None:
        self.workspace_root = workspace_root
        self.session = session
        self.execution_history: List[ToolExecutionRecord] = []

    async def execute(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: float = 60.0,
        auto_apply: bool = True,
    ) -> ToolResult:
        """Execute a normalized tool call with bounded execution and logging."""
        if isinstance(tool_name, str) and "<|channel|>" in tool_name:
            tool_name = tool_name.split("<|channel|>")[0]
        tool_def = ToolRegistry.get_tool(tool_name)
        if not tool_def:
            err_payload = {
                "error": f"Tool '{tool_name}' is not supported.",
                "tool": tool_name,
                "retryable": False
            }
            import json
            return ToolResult(
                success=False,
                output=err_payload,
                error=json.dumps(err_payload),
            )

        # Validate arguments using pydantic schema
        try:
            validated_args = tool_def.input_schema(**arguments).model_dump()
        except Exception as pydantic_err:
            err_payload = {
                "error": f"Schema validation error: {str(pydantic_err)}",
                "tool": tool_name,
                "retryable": True
            }
            import json
            return ToolResult(
                success=False,
                output=err_payload,
                error=json.dumps(err_payload),
            )

        from backend.app.infrastructure.observability.telemetry import TelemetryManager

        start_ts = time.time()
        start_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Evaluate security permissions via PermissionEngine (Step 1 & 39 requirement)
        from backend.app.agent.security import PermissionEngine, SecretRedactor
        p_engine = PermissionEngine.get_instance(self.workspace_root)
        decision = p_engine.evaluate_tool_call(
            session_id=str(getattr(self.session, "session_id", "active_session")),
            tool_name=tool_def.name,
            arguments=validated_args,
        )

        tracer = TelemetryManager.get_tracer()
        with tracer.start_as_current_span(
            f"tool.{tool_def.name}",
            attributes={
                "tool_call_id": tool_call_id,
                "tool_name": tool_def.name,
                "risk_level": tool_def.risk_level,
                "idempotent": tool_def.idempotent,
                "allowed": decision.allowed,
            }
        ) as span:
            TelemetryManager.increment_counter(
                "tool_calls_total",
                attributes={"tool_name": tool_def.name}
            )

            if not decision.allowed:
                TelemetryManager.increment_counter(
                    "tool_policy_denied_total",
                    attributes={"tool_name": tool_def.name}
                )
                return ToolResult(success=False, output=None, error=f"Security Policy Denied: {decision.reason}")

            if decision.requires_approval and not auto_apply:
                from backend.app.agent.agent_runtime.runtime import AgentState
                if hasattr(self.session, "state"):
                    self.session.state = AgentState.WAITING_FOR_APPROVAL

                # Genuinely await user confirmation if session provides a confirmation bridge
                if hasattr(self.session, "request_tool_confirmation"):
                    approved, modified_args = await self.session.request_tool_confirmation(
                        tool_call_id=tool_call_id,
                        tool_name=tool_def.name,
                        arguments=validated_args
                    )
                    if not approved:
                        TelemetryManager.increment_counter(
                            "tool_approval_denied_total",
                            attributes={"tool_name": tool_def.name}
                        )
                        if hasattr(self.session, "state"):
                            self.session.state = AgentState.EXECUTING
                        return ToolResult(
                            success=False,
                            output=None,
                            error=f"Execution of tool '{tool_def.name}' was rejected by user."
                        )
                    if modified_args and isinstance(modified_args, dict):
                        validated_args = modified_args
                    if hasattr(self.session, "state"):
                        self.session.state = AgentState.EXECUTING
                    # Explicitly override auto_apply to bypass inner legacy confirmation prompts
                    auto_apply = True
                else:
                    # In headless, automated, or non-interactive mode without confirmation callback, fail closed
                    if hasattr(self.session, "state"):
                        self.session.state = AgentState.EXECUTING
                    TelemetryManager.increment_counter(
                        "tool_approval_denied_total",
                        attributes={"tool_name": tool_def.name}
                    )
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Execution of high-risk tool '{tool_def.name}' requires explicit user approval but no interactive confirmation handler is available."
                    )

            # Apply default timeouts if requested is higher than platform allowed max
            run_timeout = min(timeout, tool_def.timeout)

            try:
                res = await asyncio.wait_for(
                    self._dispatch(tool_call_id, tool_def.name, validated_args, auto_apply=auto_apply),
                    timeout=run_timeout,
                )
                # Redact secrets from output string if text result
                if res.success and isinstance(res.output, str):
                    res.output = SecretRedactor.redact_secrets(res.output)
                
                status_lbl = "success" if res.success else "failure"
                TelemetryManager.increment_counter(
                    f"tool_{status_lbl}_total",
                    attributes={"tool_name": tool_def.name}
                )
            except asyncio.TimeoutError:
                TelemetryManager.increment_counter(
                    "tool_timeout_total",
                    attributes={"tool_name": tool_def.name}
                )
                res = ToolResult(
                    success=False,
                    output=None,
                    error=f"Tool execution '{tool_name}' timed out after {run_timeout} seconds.",
                )
            except Exception as e:
                TelemetryManager.increment_counter(
                    "tool_failure_total",
                    attributes={"tool_name": tool_def.name, "error": type(e).__name__}
                )
                res = ToolResult(
                    success=False,
                    output=None,
                    error=f"Tool execution '{tool_name}' failed: {type(e).__name__}: {str(e)}",
                )

            end_ts = time.time()
            duration_ms = (end_ts - start_ts) * 1000.0
            TelemetryManager.record_histogram(
                "tool_duration_ms",
                duration_ms,
                attributes={"tool_name": tool_def.name}
            )
            span.set_attribute("success", res.success)
            span.set_attribute("duration_ms", duration_ms)
        end_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        record = ToolExecutionRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_def.name,
            arguments=validated_args,
            start_time=start_str,
            end_time=end_str,
            duration_seconds=round(end_ts - start_ts, 4),
            success=res.success,
            output=res.output if res.success else None,
            error=res.error,
        )
        self.execution_history.append(record)
        return res

    async def _dispatch(self, tc_id: str, tool_name: str, args: Dict[str, Any], auto_apply: bool = True) -> ToolResult:
        """Internal router mapping normalized tool names to workspace operations."""
        if isinstance(tool_name, str) and "<|channel|>" in tool_name:
            tool_name = tool_name.split("<|channel|>")[0]
        name = tool_name.lower().strip()

        # Handle structural symbol tools (Step 6 & 21 requirements)
        if name in ("find_symbol", "find_definition", "find_references", "find_callers", "find_callees", "find_tests", "find_related_files"):
            from backend.app.agent.context_engine import ContextEngine
            ctx_engine = ContextEngine.get_instance(self.workspace_root)
            sym_query = args.get("symbol") or args.get("name") or args.get("path") or args.get("query") or ""

            if name in ("find_symbol", "find_definition"):
                syms = ctx_engine.symbol_index.find_symbols(sym_query)
                res_data = [
                    {
                        "symbol": s.name,
                        "file": s.file,
                        "line": s.start_line,
                        "kind": s.kind.value,
                        "language": s.language,
                    }
                    for s in syms
                ]
                return ToolResult(success=True, output=res_data)

            elif name == "find_callers":
                callers = ctx_engine.dependency_graph.find_callers(sym_query)
                res_data = [{"id": c.id, "name": c.name, "type": c.type.value, "path": c.path} for c in callers]
                return ToolResult(success=True, output=res_data)

            elif name == "find_callees":
                callees = ctx_engine.dependency_graph.find_callees(sym_query)
                res_data = [{"id": c.id, "name": c.name, "type": c.type.value, "path": c.path} for c in callees]
                return ToolResult(success=True, output=res_data)

            elif name == "find_tests":
                tests = ctx_engine.dependency_graph.find_tests(sym_query)
                return ToolResult(success=True, output={"symbol": sym_query, "tests": tests})

            elif name == "find_related_files":
                related = ctx_engine.dependency_graph.find_related_files(sym_query)
                return ToolResult(success=True, output={"file": sym_query, "related_files": related})

        # Resolve through ToolRegistry handler
        try:
            handler = ToolRegistry.get_handler(name)
        except NotImplementedError:
            raise NotImplementedError(f"Tool '{name}' is not supported.")

        bridge = _SessionBridge(self.workspace_root, self.session)

        try:
            import inspect
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())

            if "name" in params and "tc_id" in params and "auto_apply" in params:
                out = await handler(bridge, tc_id, tool_name, args, auto_apply)
            elif "tc_id" in params and "auto_apply" in params:
                out = await handler(bridge, tc_id, args, auto_apply)
            elif "tc_id" in params:
                out = await handler(bridge, tc_id, args)
            else:
                out = await handler(bridge, args)

            is_err = isinstance(out, str) and (out.lower().startswith("error") or "failed" in out.lower()[:30])
            return ToolResult(
                success=not is_err,
                output=out if not is_err else None,
                error=out if is_err else None,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
            )
