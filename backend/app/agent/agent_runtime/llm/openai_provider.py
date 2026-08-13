"""
OpenAI-Compatible LLM Provider.

Supports any OpenAI-compatible API (OpenAI, Azure, Groq, Ollama, LMStudio, etc.)
via configurable ``base_url``.
"""

from __future__ import annotations

import json
import time
import logging
from typing import Any, Optional

from agent_runtime.llm import (
    LLMProvider,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolSchema,
)

logger = logging.getLogger("agent_runtime.llm.openai_provider")


# Approximate pricing per 1M tokens (USD) — used for cost estimation only.
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "o3-mini": {"input": 1.10, "output": 4.40},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts and model name."""
    pricing = _MODEL_PRICING.get(model)
    if not pricing:
        # Try prefix matching for versioned models
        for key, val in _MODEL_PRICING.items():
            if model.startswith(key):
                pricing = val
                break
    if not pricing:
        return 0.0
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def _messages_to_openai(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert internal Message objects to OpenAI API format."""
    result = []
    for msg in messages:
        entry: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        if msg.name:
            entry["name"] = msg.name
        result.append(entry)
    return result


def _tools_to_openai(tools: list[ToolSchema]) -> list[dict[str, Any]]:
    """Convert internal ToolSchema objects to OpenAI tools format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI-compatible APIs.

    Uses ``httpx`` for async HTTP requests (no openai SDK dependency required).

    Args:
        api_key: API key for authentication.
        model: Model name (e.g. ``gpt-4o``, ``gpt-4.1-mini``).
        base_url: API base URL. Defaults to OpenAI's API.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import httpx

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Load from config manager defaults if not overridden
        temp = temperature
        max_tok = max_tokens
        top_p = 1.0
        seed = None
        try:
            from backend.app.config import config_manager
            if temperature == 0.0:
                temp = config_manager.get_temperature()
            if max_tokens == 4096:
                max_tok = config_manager.get_max_tokens()
            top_p = config_manager.get_top_p()
            seed = config_manager.get_seed()
        except Exception:
            pass

        body: dict[str, Any] = {
            "model": self.model,
            "messages": _messages_to_openai(messages),
            "temperature": temp,
            "max_tokens": max_tok,
            "top_p": top_p,
        }
        if seed is not None:
            # Only send 'seed' to native OpenAI; third-party endpoints (NVIDIA, Google, etc.)
            # reject it with 400 "Cannot find field".
            _provider_url = self.base_url.lower()
            if not _provider_url or "openai.com" in _provider_url:
                body["seed"] = seed

        if tools:
            body["tools"] = _tools_to_openai(tools)
            body["tool_choice"] = "auto"

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.monotonic() - start) * 1000

        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Parse tool calls if present
        tool_calls: list[ToolCallRequest] = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {"_raw": args_str}
                tool_calls.append(ToolCallRequest(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=args,
                ))

        finish_reason = choice.get("finish_reason", "stop")
        if finish_reason == "tool_calls":
            pass  # keep as-is
        elif tool_calls:
            finish_reason = "tool_calls"

        cost = _estimate_cost(self.model, input_tokens, output_tokens)

        logger.info(
            "LLM call: model=%s, input=%d, output=%d, cost=$%.4f, latency=%.0fms, tool_calls=%d",
            self.model, input_tokens, output_tokens, cost, latency_ms, len(tool_calls),
        )

        return LLMResponse(
            content=msg.get("content", "") or "",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=data.get("model", self.model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> bool:
        """Ping the models endpoint to verify connectivity."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False
