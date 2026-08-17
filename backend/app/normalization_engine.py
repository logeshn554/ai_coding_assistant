"""Central Normalization Engine — Standardizes prompts, workspace paths, tool outputs, model responses, and errors."""
import logging
import os
from typing import Any

logger = logging.getLogger("loopix.normalization_engine")

class NormalizationEngine:
    def normalize_prompt(self, raw_prompt: str) -> dict[str, Any]:
        """Normalize raw user prompt text into structured intent & target module metadata."""
        if not raw_prompt:
            return {"intent": "general_query", "module": "workspace", "priority": "normal"}

        lower = raw_prompt.lower()
        intent = "general_query"
        module = "workspace"
        priority = "normal"

        if any(k in lower for k in ["fix", "bug", "broken", "repair", "error", "fail"]):
            intent = "fix_bug"
            priority = "high"
        elif any(k in lower for k in ["create", "build", "add", "implement", "generate"]):
            intent = "build_feature"
        elif any(k in lower for k in ["refactor", "clean", "optimize", "improve"]):
            intent = "refactor_code"

        if "auth" in lower or "login" in lower or "jwt" in lower:
            module = "authentication"
        elif "db" in lower or "database" in lower or "sql" in lower or "schema" in lower:
            module = "database"
        elif "ui" in lower or "component" in lower or "css" in lower or "frontend" in lower:
            module = "frontend"

        return {
            "raw_prompt": raw_prompt,
            "intent": intent,
            "module": module,
            "priority": priority
        }

    def normalize_tool_output(self, tool_name: str, raw_payload: Any, status: str = "success") -> dict[str, Any]:
        """Wrap tool outputs into a unified execution response envelope."""
        return {
            "tool": tool_name,
            "status": status,
            "payload": raw_payload if isinstance(raw_payload, (dict, list)) else {"result": str(raw_payload)},
            "metadata": {"timestamp_epoch": os.environ.get("TIMESTAMP", "1785170000")}
        }

    def normalize_model_output(self, summary: str = "", edits: list[Any] = None, tool_calls: list[Any] = None) -> dict[str, Any]:
        """Normalize multi-provider LLM outputs (GPT, Claude, Gemini, DeepSeek, Qwen) into a standard schema."""
        return {
            "summary": summary,
            "edits": edits or [],
            "tool_calls": tool_calls or [],
            "warnings": []
        }

    def normalize_error(self, exc: Exception, error_type: str = "runtime") -> dict[str, Any]:
        """Normalize exceptions into a unified severity & recovery envelope."""
        msg = str(exc)
        severity = "medium"
        recoverable = True

        if "PermissionError" in type(exc).__name__ or "Access denied" in msg:
            severity = "high"
            recoverable = False
        elif "SyntaxError" in type(exc).__name__:
            severity = "medium"

        return {
            "type": error_type,
            "exception": type(exc).__name__,
            "message": msg,
            "severity": severity,
            "recoverable": recoverable
        }

normalization_engine = NormalizationEngine()
