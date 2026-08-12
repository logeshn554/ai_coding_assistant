"""
Model Response Normalization Layer — Step 4 requirement.

Normalizes model responses from OpenAI, Anthropic, Gemini, Ollama, local models, etc.
into one canonical ModelResponse and ToolCall structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger("devpilot.agent_runtime.llm_adapter")


@dataclass
class ToolCall:
    """Normalized tool call structure."""
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """Canonical model response representation."""
    text: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None


class ModelResponseNormalizer:
    """Normalizes raw responses or streaming chunks from model adapters."""

    @staticmethod
    def normalize_tool_call(raw: Any) -> ToolCall:
        """Convert various raw tool call representations into a canonical ToolCall."""
        if isinstance(raw, ToolCall):
            return raw

        if isinstance(raw, dict):
            tc_id = raw.get("id") or raw.get("tool_call_id") or f"tc_{hash(str(raw))}"
            tc_name = raw.get("name") or raw.get("function", {}).get("name") or ""
            args = raw.get("arguments") or raw.get("input") or raw.get("function", {}).get("arguments") or {}

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}

            return ToolCall(id=str(tc_id), name=str(tc_name), arguments=dict(args))

        # Handle object attributes (e.g. LangChain / OpenAI SDK objects)
        tc_id = getattr(raw, "id", None) or f"tc_{id(raw)}"
        tc_name = getattr(raw, "name", None) or getattr(getattr(raw, "function", None), "name", "")
        args = getattr(raw, "arguments", None) or getattr(raw, "input", None) or getattr(getattr(raw, "function", None), "arguments", {})

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"raw": args}

        return ToolCall(id=str(tc_id), name=str(tc_name), arguments=dict(args) if isinstance(args, dict) else {})

    @classmethod
    def normalize_response(
        self,
        raw_response: Any,
        text_content: Optional[str] = None,
        raw_tool_calls: Optional[List[Any]] = None,
        finish_reason: Optional[str] = None,
    ) -> ModelResponse:
        """Construct a ModelResponse, falling back to text parsing if no native tool calls present."""
        tool_calls: List[ToolCall] = []

        if raw_tool_calls:
            for tc in raw_tool_calls:
                try:
                    normalized = self.normalize_tool_call(tc)
                    if normalized.name:
                        tool_calls.append(normalized)
                except Exception as e:
                    logger.warning(f"Failed to normalize native tool call {tc}: {e}")

        # Check raw_response object if passed directly
        if raw_response and not tool_calls:
            r_tool_calls = getattr(raw_response, "tool_calls", None)
            if isinstance(r_tool_calls, list):
                for tc in r_tool_calls:
                    try:
                        normalized = self.normalize_tool_call(tc)
                        if normalized.name:
                            tool_calls.append(normalized)
                    except Exception as e:
                        logger.warning(f"Failed to normalize raw_response tool call {tc}: {e}")

            if not text_content:
                text_content = getattr(raw_response, "content", None) or getattr(raw_response, "text", None)

            if not finish_reason:
                finish_reason = getattr(raw_response, "finish_reason", None)

        # Fallback: Textual/regex parsing ONLY if no native tool calls were present
        if not tool_calls and text_content:
            fallback_tc = self._extract_fallback_tool_call(text_content)
            if fallback_tc:
                tool_calls.append(fallback_tc)

        return ModelResponse(
            text=text_content,
            tool_calls=tool_calls,
            finish_reason=finish_reason or ("tool_use" if tool_calls else "end_turn"),
        )

    @staticmethod
    def _extract_fallback_tool_call(text: str) -> Optional[ToolCall]:
        """Regex/JSON compatibility fallback for non-native function calling models."""
        patterns = [
            r"```json\s*(\{\s*\"tool\"|\{\s*\"name\"|\{\s*\"action\"[^\}]+\})\s*```",
            r"(\{\s*\"name\"\s*:\s*\"[^\"]+\"\s*,\s*\"arguments\"\s*:\s*\{[^\}]*\}\s*\})",
            r"(\{\s*\"action\"\s*:\s*\"[^\"]+\"\s*,\s*\"action_input\"\s*:\s*\{[^\}]*\}\s*\})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    name = data.get("name") or data.get("tool") or data.get("action")
                    args = data.get("arguments") or data.get("input") or data.get("action_input") or {}
                    if name:
                        import uuid
                        return ToolCall(
                            id=f"fallback_{uuid.uuid4().hex[:8]}",
                            name=str(name),
                            arguments=args if isinstance(args, dict) else {"input": args},
                        )
                except Exception:
                    pass
        return None
