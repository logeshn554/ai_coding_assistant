"""
Common LLM Adapters — Implements OpenAI-compatible protocol adapter and Anthropic adapter.
"""

from __future__ import annotations

import time
import asyncio
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from agent_os.providers.base import (
    ModelProvider,
    ProviderConfig,
    ModelResponse,
    ToolCall,
    TokenUsage,
    ProviderHealth,
)

logger = logging.getLogger("agent_os.providers.common_adapter")


class CommonAdapter(ModelProvider):
    """Generic adapter for OpenAI-compatible APIs (OpenAI, Gemini, Groq, OpenRouter, Ollama, etc.)."""

    async def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            api_key=self.config.api_key or "mock-key",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # Convert tool definitions to OpenAI format if needed
        openai_tools = None
        if tools:
            openai_tools = []
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    }
                })

        try:
            call_kwargs = {
                "model": self.config.model,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", getattr(self.config, "top_p", 1.0)),
            }
            seed_val = kwargs.get("seed", getattr(self.config, "seed", None))
            if seed_val is not None:
                call_kwargs["seed"] = seed_val
            if openai_tools:
                call_kwargs["tools"] = openai_tools
                call_kwargs["tool_choice"] = "auto"

            response = await client.chat.completions.create(**call_kwargs)
            
            choice = response.choices[0]
            message = choice.message
            
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    import json
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {"_raw": tc.function.arguments}
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args
                    ))

            usage = None
            if response.usage:
                usage = TokenUsage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )

            return ModelResponse(
                content=message.content or "",
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason,
                usage=usage,
                model=response.model,
                provider=self.config.name,
            )

        except Exception as e:
            logger.error(f"OpenAI adapter request failed: {e}")
            raise

    async def stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            api_key=self.config.api_key or "mock-key",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        try:
            call_kwargs = {
                "model": self.config.model,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", getattr(self.config, "top_p", 1.0)),
            }
            seed_val = kwargs.get("seed", getattr(self.config, "seed", None))
            if seed_val is not None:
                call_kwargs["seed"] = seed_val

            stream_val = kwargs.get("stream", getattr(self.config, "stream", True))
            if not stream_val:
                call_kwargs["stream"] = False
                response = await client.chat.completions.create(**call_kwargs)
                content = response.choices[0].message.content
                if content:
                    yield content
                return

            call_kwargs["stream"] = True
            response = await client.chat.completions.create(**call_kwargs)
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"OpenAI adapter streaming failed: {e}")
            raise

    async def health_check(self) -> ProviderHealth:
        import httpx
        start = time.monotonic()
        
        # Fast, low-resource health ping to models list or health check endpoint
        url = f"{self.config.base_url}/models"
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                latency = (time.monotonic() - start) * 1000
                if resp.status_code == 200:
                    return ProviderHealth(healthy=True, latency_ms=latency)
                else:
                    return ProviderHealth(healthy=False, latency_ms=latency, error=f"Status code {resp.status_code}")
        except Exception as e:
            return ProviderHealth(healthy=False, latency_ms=0.0, error=str(e))


class AnthropicAdapter(ModelProvider):
    """Adapter specifically for Anthropic's Claude models using the native anthropic library."""

    async def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        import anthropic
        
        client = anthropic.AsyncAnthropic(
            api_key=self.config.api_key or "mock-key",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

        formatted_messages = []
        system_prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system_prompt = msg.get("content", "")
            else:
                formatted_messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })

        # Convert tool definitions to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for tool in tools:
                anthropic_tools.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("input_schema", {}),
                })

        try:
            call_kwargs = {
                "model": self.config.model,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", getattr(self.config, "top_p", 1.0)),
            }
            if system_prompt:
                call_kwargs["system"] = system_prompt
            if anthropic_tools:
                call_kwargs["tools"] = anthropic_tools

            response = await client.messages.create(**call_kwargs)
            
            content = ""
            tool_calls = []
            
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input
                    ))

            usage = None
            if response.usage:
                usage = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                )

            return ModelResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=response.stop_reason,
                usage=usage,
                model=self.config.model,
                provider=self.config.name,
            )

        except Exception as e:
            logger.error(f"Anthropic adapter request failed: {e}")
            raise

    async def stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        import anthropic
        
        client = anthropic.AsyncAnthropic(
            api_key=self.config.api_key or "mock-key",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

        formatted_messages = []
        system_prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system_prompt = msg.get("content", "")
            else:
                formatted_messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })

        try:
            call_kwargs = {
                "model": self.config.model,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", getattr(self.config, "top_p", 1.0)),
            }
            if system_prompt:
                call_kwargs["system"] = system_prompt

            stream_val = kwargs.get("stream", getattr(self.config, "stream", True))
            if not stream_val:
                response = await client.messages.create(**call_kwargs)
                content = ""
                for block in response.content:
                    if block.type == "text":
                        content += block.text
                if content:
                    yield content
                return

            async with client.messages.stream(**call_kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic adapter streaming failed: {e}")
            raise

    async def health_check(self) -> ProviderHealth:
        import anthropic
        start = time.monotonic()
        
        client = anthropic.AsyncAnthropic(
            api_key=self.config.api_key or "mock-key",
            base_url=self.config.base_url,
            timeout=5.0,
        )
        try:
            await client.messages.create(
                model=self.config.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "OK"}],
            )
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(healthy=True, latency_ms=latency)
        except Exception as e:
            return ProviderHealth(healthy=False, latency_ms=0.0, error=str(e))
