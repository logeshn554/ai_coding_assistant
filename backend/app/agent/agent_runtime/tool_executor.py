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
            except Exception:
                pass

    def log_audit(self, *args, **kwargs):
        if self.inner_session and hasattr(self.inner_session, "log_audit"):
            try:
                self.inner_session.log_audit(*args, **kwargs)
            except Exception:
                pass
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
    ) -> ToolResult:
        """Execute a normalized tool call with bounded execution and logging."""
        start_ts = time.time()
        start_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Evaluate security permissions via PermissionEngine (Step 1 & 39 requirement)
        from backend.app.agent.security import PermissionEngine, SecretRedactor
        p_engine = PermissionEngine.get_instance(self.workspace_root)
        decision = p_engine.evaluate_tool_call(
            session_id=str(getattr(self.session, "session_id", "active_session")),
            tool_name=tool_name,
            arguments=arguments,
        )

        if not decision.allowed:
            return ToolResult(success=False, output=None, error=f"Security Policy Denied: {decision.reason}")

        try:
            res = await asyncio.wait_for(
                self._dispatch(tool_call_id, tool_name, arguments),
                timeout=timeout,
            )
            # Redact secrets from output string if text result
            if res.success and isinstance(res.output, str):
                res.output = SecretRedactor.redact_secrets(res.output)
        except asyncio.TimeoutError:
            res = ToolResult(
                success=False,
                output=None,
                error=f"Tool execution '{tool_name}' timed out after {timeout} seconds.",
            )
        except Exception as e:
            res = ToolResult(
                success=False,
                output=None,
                error=f"Tool execution '{tool_name}' failed: {type(e).__name__}: {str(e)}",
            )

        end_ts = time.time()
        end_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        record = ToolExecutionRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=arguments,
            start_time=start_str,
            end_time=end_str,
            duration_seconds=round(end_ts - start_ts, 4),
            success=res.success,
            output=res.output if res.success else None,
            error=res.error,
        )
        self.execution_history.append(record)
        return res

    async def _dispatch(self, tc_id: str, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Internal router mapping normalized tool names to workspace operations."""
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

        from backend.app.tools.dispatcher import dispatch_tool
        bridge = _SessionBridge(self.workspace_root, self.session)

        try:
            out = await dispatch_tool(bridge, tc_id, name, args, True)
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
