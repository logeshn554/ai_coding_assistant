"""
OpenAI-Compatible LLM Provider.

Supports any OpenAI-compatible API (OpenAI, Azure, Groq, Ollama, LMStudio, etc.)
via configurable ``base_url``.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from agent_runtime.llm import (
    LLMProvider,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolSchema,
)

logger = logging.getLogger("agent_runtime.llm.openai_provider")


import asyncio
import random

import httpx


async def _call_with_retry(client: httpx.AsyncClient, url: str, headers: dict, json_body: dict) -> httpx.Response:
    max_retries = 3
    base_delay = 1.0
    max_delay = 10.0
    
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.post(url, headers=headers, json=json_body)
            resp.raise_for_status()
            return resp
        except Exception as e:
            err_str = str(e).lower()
            status_code = getattr(getattr(e, 'response', None), 'status_code', None) or getattr(e, 'status_code', None)
            
            is_rate_limit = status_code == 429 or any(kw in err_str for kw in ("rate limit", "rate_limit", "ratelimit", "too many requests", "429"))
            is_server_error = (status_code is not None and status_code >= 500) or any(kw in err_str for kw in ("server error", "502 bad gateway", "503 service unavailable", "504 gateway timeout", "500 internal server error"))
            is_timeout = isinstance(e, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)) or any(kw in err_str for kw in ("timeout", "timed out", "connecttimeout", "readtimeout"))
            
            if (is_rate_limit or is_server_error or is_timeout) and attempt < max_retries:
                delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1), max_delay)
                logger.warning(
                    f"LLM API call failed (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"LLM API call failed permanently after {attempt} attempts: {e}")
                raise e


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    input_cost_per_m: float | None = None,
    output_cost_per_m: float | None = None,
) -> float:
    """Estimate USD cost from explicit per-million rates (no hardcoded model table)."""
    import os

    in_rate = input_cost_per_m
    out_rate = output_cost_per_m
    if in_rate is None:
        env_in = os.environ.get("LOOPIX_INPUT_COST_PER_M")
        if env_in:
            try:
                in_rate = float(env_in)
            except ValueError:
                pass
    if out_rate is None:
        env_out = os.environ.get("LOOPIX_OUTPUT_COST_PER_M")
        if env_out:
            try:
                out_rate = float(env_out)
            except ValueError:
                pass
    if in_rate is None or out_rate is None:
        return 0.0
    return (input_tokens * float(in_rate) + output_tokens * float(out_rate)) / 1_000_000


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
        model: Model name from user/config (required — no hardcoded default).
        base_url: API base URL. Defaults to OpenAI's API.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
    ) -> None:
        import os
        resolved = (model or os.environ.get("LOOPIX_MODEL") or "").strip()
        if not resolved:
            raise ValueError(
                "OpenAIProvider requires a model name via constructor or LOOPIX_MODEL. "
                "No hardcoded model defaults are allowed."
            )
        self.api_key = api_key
        self.model = resolved
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
            resp = await _call_with_retry(client, url, headers, body)
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
