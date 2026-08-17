"""Phase 13 — Execution Logger.

Structured JSON logging for every agent execution.
Provides full observability into agent decisions.

Log fields:
  session_id        — session identifier
  intent            — classified intent type
  context_collected — list of auto-read files
  plan_steps        — task graph steps
  tool_calls        — list of {name, args, result, status}
  validation_results — validator output
  critic_result     — critic pass/fail
  stop_reason       — why the agent stopped
  total_turns       — number of LLM turns used
  cost_usd          — total API cost
  duration_s        — wall-clock execution time
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("loopix.agent.execution_logger")


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result: str = ""
    status: str = "pending"  # "success", "error", "skipped"
    duration_s: float = 0.0
    retry_count: int = 0


@dataclass
class ExecutionLog:
    session_id: str = ""
    intent: str = "GENERAL"
    goal: str = ""
    context_collected: list[str] = field(default_factory=list)
    plan_steps: list[dict] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    validation_results: dict = field(default_factory=dict)
    critic_result: str = ""
    stop_reason: str = ""
    total_turns: int = 0
    cost_usd: float = 0.0
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float = 0.0

    @property
    def duration_s(self) -> float:
        if self.ended_at:
            return round(self.ended_at - self.started_at, 2)
        return round(time.monotonic() - self.started_at, 2)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "intent": self.intent,
            "goal": self.goal[:300] if self.goal else "",
            "context_collected": self.context_collected,
            "plan_steps": self.plan_steps,
            "tool_calls": [
                {
                    "name": t.name,
                    "args": {k: str(v)[:200] for k, v in (t.args or {}).items()},
                    "result": t.result[:500] if t.result else "",
                    "status": t.status,
                    "duration_s": round(t.duration_s, 3),
                    "retry_count": t.retry_count,
                }
                for t in self.tool_calls
            ],
            "validation_results": self.validation_results,
            "critic_result": self.critic_result,
            "stop_reason": self.stop_reason,
            "total_turns": self.total_turns,
            "cost_usd": round(self.cost_usd, 6),
            "duration_s": self.duration_s,
        }


class ExecutionLogger:
    """Records structured execution logs for a single agent run.

    Usage:
        exec_log = ExecutionLogger(session_id)
        exec_log.set_intent("BUG_FIX", goal="Fix login error")
        exec_log.record_context_file("auth.py")
        exec_log.record_tool_call("read_file", {"path": "auth.py"}, result="...", status="success")
        exec_log.finish("completed")
        exec_log.emit()  # Logs to loopix.agent.execution_logger as JSON
    """

    def __init__(self, session_id: str):
        self._log = ExecutionLog(session_id=session_id)
        self._current_tool: ToolCallRecord | None = None
        self._current_tool_start: float = 0.0

    def set_intent(self, intent: str, goal: str = "") -> None:
        self._log.intent = intent
        self._log.goal = goal

    def set_plan(self, steps: list[dict]) -> None:
        self._log.plan_steps = [
            {"id": s.get("id"), "task": s.get("task", ""), "type": s.get("type", "general")}
            for s in steps
        ]

    def record_context_file(self, path: str) -> None:
        if path not in self._log.context_collected:
            self._log.context_collected.append(path)

    def start_tool_call(self, name: str, args: dict) -> None:
        """Call before dispatching a tool."""
        self._current_tool = ToolCallRecord(name=name, args=args or {})
        self._current_tool_start = time.monotonic()

    def finish_tool_call(self, result: str = "", status: str = "success", retry_count: int = 0) -> None:
        """Call after tool returns."""
        if self._current_tool:
            self._current_tool.result = result[:1000] if result else ""
            self._current_tool.status = status
            self._current_tool.duration_s = time.monotonic() - self._current_tool_start
            self._current_tool.retry_count = retry_count
            self._log.tool_calls.append(self._current_tool)
            self._current_tool = None

    def set_validation(self, results: dict) -> None:
        self._log.validation_results = results

    def set_critic(self, result: str) -> None:
        self._log.critic_result = result

    def increment_turns(self) -> None:
        self._log.total_turns += 1

    def set_cost(self, cost_usd: float) -> None:
        self._log.cost_usd = cost_usd

    def finish(self, stop_reason: str) -> None:
        self._log.stop_reason = stop_reason
        self._log.ended_at = time.monotonic()

    def emit(self) -> None:
        """Write the structured log as a single JSON line to the logger."""
        try:
            data = self._log.to_dict()
            logger.info(json.dumps(data))
        except Exception as e:
            logger.warning(f"Failed to emit execution log: {e}")

    def to_dict(self) -> dict:
        return self._log.to_dict()
