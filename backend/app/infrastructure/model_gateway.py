import os
import json
import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Type, AsyncGenerator
from pydantic import BaseModel
from backend.app.config import settings

logger = logging.getLogger("devpilot.infrastructure.model_gateway")

class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0

class GatewayModelResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = []
    finish_reason: Optional[str] = None
    usage: TokenUsage
    provider: str
    model: str
    metadata: Dict[str, Any] = {}

class ModelGateway:
    """Canonical model gateway implementing retry-backoff, timeouts, and provider failover."""

    @staticmethod
    async def generate_stream(
        profile: dict,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        task_type: str = "general",
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chunks from LLM with exponential backoff retries for transient errors."""
        from backend.app.adapters.router import ModelRouter
        from backend.app.infrastructure.observability.telemetry import TelemetryManager

        router = ModelRouter()
        adapter = router.get_adapter(profile, is_agent=True, task_type=task_type)
        provider = profile.get("provider", "unknown")
        model = profile.get("model_name") or profile.get("model") or "unknown"

        tracer = TelemetryManager.get_tracer()
        span = tracer.start_span(
            "model.request",
            attributes={
                "provider": provider,
                "model": model,
                "task_type": task_type,
            }
        )
        try:
            TelemetryManager.increment_counter(
                "model_requests_total",
                attributes={"provider": provider, "model": model, "task_type": task_type}
            )

            attempt = 0
            start_ts = time.perf_counter()

            while attempt <= max_retries:
                try:
                    async for chunk in adapter.stream_chat(messages, tools or [], system_prompt):
                        if chunk.get("type") == "usage":
                            in_tokens = chunk.get("input_tokens", 0)
                            out_tokens = chunk.get("output_tokens", 0)
                            cost = chunk.get("cost_usd", 0.0)
                            TelemetryManager.increment_counter(
                                "model_input_tokens_total",
                                amount=in_tokens,
                                attributes={"provider": provider, "model": model}
                            )
                            TelemetryManager.increment_counter(
                                "model_output_tokens_total",
                                amount=out_tokens,
                                attributes={"provider": provider, "model": model}
                            )
                            TelemetryManager.record_histogram(
                                "model_cost_usd",
                                cost,
                                attributes={"provider": provider, "model": model}
                            )
                            span.set_attribute("input_tokens", in_tokens)
                            span.set_attribute("output_tokens", out_tokens)
                            span.set_attribute("cost_usd", cost)
                        yield chunk
                    
                    duration_ms = (time.perf_counter() - start_ts) * 1000.0
                    TelemetryManager.record_histogram(
                        "model_latency_ms",
                        duration_ms,
                        attributes={"provider": provider, "model": model}
                    )
                    break

                except Exception as e:
                    attempt += 1
                    span.set_attribute("error", True)
                    span.set_attribute("error_message", str(e))
                    TelemetryManager.increment_counter(
                        "model_failures_total",
                        attributes={"provider": provider, "model": model, "error": type(e).__name__}
                    )

                    err_msg = str(e).lower()
                    is_transient = any(
                        sig in err_msg for sig in (
                            "timeout", "rate limit", "429", "500", "502", "503", "504",
                            "connection", "network", "temporary"
                        )
                    )
                    
                    if attempt > max_retries or not is_transient:
                        logger.error(f"ModelGateway non-recoverable error or max retries exceeded: {e}")
                        failover_profile = profile.get("failover_profile")
                        if failover_profile and attempt > max_retries:
                            logger.warning("Attempting failover to secondary provider/model...")
                            TelemetryManager.increment_counter(
                                "model_failover_total",
                                attributes={"from_provider": provider, "from_model": model}
                            )
                            async for chunk in ModelGateway.generate_stream(
                                failover_profile, messages, tools, system_prompt, task_type, max_retries=1
                            ):
                                yield chunk
                            return
                        raise e

                    delay = base_delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                    # Extract explicit retry-after if provided by Gemini / OpenAI rate limits
                    import re
                    retry_sec_match = re.search(r"retry in ([\d\.]+)s", str(e), re.IGNORECASE) or re.search(r"retryDelay': '(\d+)s", str(e))
                    if retry_sec_match:
                        try:
                            parsed_delay = float(retry_sec_match.group(1)) + 1.0
                            delay = min(parsed_delay, 45.0)
                        except Exception:
                            pass
                    elif hasattr(e, "retry_after_seconds") and getattr(e, "retry_after_seconds", 0) > 0:
                        delay = min(getattr(e, "retry_after_seconds") + 1.0, 45.0)

                    logger.warning(f"Transient error: '{e}'. Retrying attempt {attempt}/{max_retries} in {delay:.2f}s...")
                    TelemetryManager.increment_counter(
                        "model_retry_total",
                        attributes={"provider": provider, "model": model}
                    )
                    await asyncio.sleep(delay)
        finally:
            span.end()
