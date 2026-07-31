import json
import logging
import asyncio
import os
from typing import AsyncGenerator, List, Dict, Any, Optional

logger = logging.getLogger("devpilot.adapters.llm")

# Try to import SDKs
try:
    from openai import AsyncOpenAI
except ImportError:
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            raise ImportError("OpenAI SDK is not installed. Install 'openai' package to use this adapter.")
        async def chat(self, *args, **kwargs):
            raise NotImplementedError("OpenAI SDK not available.")

try:
    from anthropic import AsyncAnthropic
except ImportError:
    class AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            raise ImportError("Anthropic SDK is not installed. Install 'anthropic' package to use this adapter.")
        async def messages(self, *args, **kwargs):
            raise NotImplementedError("Anthropic SDK not available.")

from .base import ModelAdapter

class LLMAdapter(ModelAdapter):
    """
    Unified LLM adapter for both Anthropic and OpenAI.
    Provider-specific behaviors are routed internally based on self.provider.
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, provider: str):
        super().__init__(api_key, base_url, model_name)
        self.provider = provider

    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Shared: auto-invoke scan_for_bugs and inject its report if requested.
        messages = await self.maybe_inject_bug_scan(messages, tools)

        if self.provider == "anthropic":
            async for chunk in self._stream_anthropic(messages, tools, system_prompt):
                yield chunk
        else:
            async for chunk in self._stream_openai(messages, tools, system_prompt):
                yield chunk

    async def _stream_anthropic(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        base_url = self.base_url
        if not base_url or "api.anthropic.com" in base_url:
            base_url = None
            
        api_key = self.api_key if self.api_key else "dummy-key"
        client = AsyncAnthropic(api_key=api_key, base_url=base_url)

        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            })

        anthropic_messages = self._to_anthropic_messages(messages)
        is_agent_mode = "OPERATING MODE: Agent" in system_prompt or "MULTI-AGENT ORCHESTRATION" in system_prompt
        try:
            kwargs = {
                "model": self.model_name,
                "system": system_prompt,
                "messages": anthropic_messages,
                "tools": anthropic_tools,
                "stream": True,
            }
            if is_agent_mode:
                kwargs["max_tokens"] = 16000
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": 10000
                }
            else:
                kwargs["max_tokens"] = 4000

            stream = await client.messages.create(**kwargs)
            current_tool_calls = {}

            async for chunk in stream:
                if chunk.type == "content_block_start":
                    idx = chunk.index
                    block = chunk.content_block
                    if block.type == "tool_use":
                        current_tool_calls[idx] = {
                            "id": block.id,
                            "name": block.name,
                            "input_accumulator": ""
                        }
                    elif block.type in ("thinking", "redacted_thinking"):
                        current_tool_calls[idx] = {
                            "_thinking_type": block.type,
                            "thinking_accumulator": "",
                            "signature": getattr(block, "signature", None),
                            "data": getattr(block, "data", None),
                        }
                elif chunk.type == "content_block_delta":
                    idx = chunk.index
                    delta = chunk.delta
                    if delta.type == "text_delta":
                        yield self.build_text_chunk(delta.text)
                    elif delta.type == "input_json_delta":
                        if idx in current_tool_calls and "input_accumulator" in current_tool_calls[idx]:
                            current_tool_calls[idx]["input_accumulator"] += delta.partial_json
                    elif delta.type == "thinking_delta":
                        if idx in current_tool_calls and "thinking_accumulator" in current_tool_calls[idx]:
                            current_tool_calls[idx]["thinking_accumulator"] += getattr(delta, "thinking", "")
                    elif delta.type == "signature_delta":
                        if idx in current_tool_calls and "signature" in current_tool_calls[idx]:
                            current_tool_calls[idx]["signature"] = getattr(delta, "signature", None)
                elif chunk.type == "content_block_stop":
                    idx = chunk.index
                    if idx in current_tool_calls:
                        tc = current_tool_calls[idx]
                        if "_thinking_type" in tc:
                            if tc["_thinking_type"] == "thinking":
                                yield {
                                    "type": "thinking",
                                    "thinking": tc["thinking_accumulator"],
                                    "signature": tc["signature"],
                                }
                            else:
                                yield {
                                    "type": "redacted_thinking",
                                    "data": tc["data"],
                                }
                            del current_tool_calls[idx]
                        else:
                            raw_json = tc["input_accumulator"]
                            parsed_input, error_msg = self.parse_tool_arguments(tc["name"], raw_json)
                            yield self.build_tool_call_chunk(tc["id"], tc["name"], parsed_input, error_msg)
                            del current_tool_calls[idx]
                elif chunk.type == "message_delta":
                    stop_reason = getattr(chunk.delta, "stop_reason", None)
                    if stop_reason == "tool_use":
                        yield self.build_done_chunk("tool_use")
                    elif stop_reason in ("end_turn", "stop_sequence"):
                        yield self.build_done_chunk("stop")
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage = chunk.usage
                        yield self.build_usage_chunk(
                            getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0)
                        )
            yield self.build_done_chunk("stop")
        except Exception as e:
            logger.error(f"Anthropic API Error: {str(e)}")
            raise e

    async def _stream_openai(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        base_url = self.base_url if self.base_url else None
        api_key = self.api_key if self.api_key else "dummy-key"
        timeout_val = float(os.environ.get("OPENAI_TIMEOUT", "60.0"))
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_val)

        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })

        openai_messages = self._to_openai_messages(messages, system_prompt)
        try:
            kwargs = {
                "model": self.model_name,
                "messages": openai_messages,
                "stream": True
            }
            if openai_tools:
                kwargs["tools"] = openai_tools

            tool_calls_accum = {}
            try:
                response = await client.chat.completions.create(**kwargs)
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if getattr(delta, "content", None) is not None:
                        yield self.build_text_chunk(delta.content)
                    if getattr(delta, "tool_calls", None) is not None:
                        for tc_chunk in delta.tool_calls:
                            idx = tc_chunk.index
                            if idx not in tool_calls_accum:
                                tool_calls_accum[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                    "thought_signature": None
                                }
                            if getattr(tc_chunk, "id", None) is not None:
                                tool_calls_accum[idx]["id"] = tc_chunk.id
                            if getattr(tc_chunk, "function", None) is not None:
                                func = tc_chunk.function
                                if getattr(func, "name", None) is not None:
                                    tool_calls_accum[idx]["name"] = func.name
                                if getattr(func, "arguments", None) is not None:
                                    tool_calls_accum[idx]["arguments"] += func.arguments
                            try:
                                def get_nested_val(obj, *keys):
                                    for key in keys:
                                        if obj is None:
                                            return None
                                        if isinstance(obj, dict):
                                            obj = obj.get(key)
                                        else:
                                            obj = getattr(obj, key, None)
                                    return obj
                                sig = get_nested_val(tc_chunk, "extra_content", "google", "thought_signature")
                                if sig:
                                    tool_calls_accum[idx]["thought_signature"] = sig
                            except Exception as e:
                                logger.debug(f"Failed to extract thought_signature: {e}")

                for idx, tc in tool_calls_accum.items():
                    tc_id = tc["id"] or f"call_{idx}"
                    parsed_input, error_msg = self.parse_tool_arguments(tc["name"], tc["arguments"])
                    yield self.build_tool_call_chunk(
                        tc_id, tc["name"], parsed_input, error_msg, tc.get("thought_signature")
                    )
                stop_reason = "tool_use" if tool_calls_accum else "stop"
                yield self.build_done_chunk(stop_reason)
            except Exception as stream_err:
                err_str = str(stream_err).lower()
                is_timeout = "timeout" in err_str or "timed out" in err_str or "connecttimeout" in err_str
                if is_timeout:
                    logger.error(f"OpenAI API request timed out ({stream_err})")
                    raise TimeoutError(f"Request timed out connecting to provider ({base_url or 'OpenAI API'}). Please check network or model endpoint.") from stream_err

                if openai_tools:
                    logger.warning(f"Streaming failed with tools ({stream_err}), falling back to non-streaming request.")
                    kwargs["stream"] = False
                    try:
                        non_stream_resp = await client.chat.completions.create(**kwargs)
                        if not non_stream_resp.choices:
                            yield self.build_done_chunk("stop")
                            return
                        choice = non_stream_resp.choices[0]
                        msg = choice.message
                        if getattr(msg, "content", None):
                            yield self.build_text_chunk(msg.content)
                        tcs = getattr(msg, "tool_calls", None)
                        if tcs:
                            for idx, tc in enumerate(tcs):
                                tc_id = tc.id or f"call_{idx}"
                                parsed_input, error_msg = self.parse_tool_arguments(
                                    tc.function.name, tc.function.arguments
                                )
                                yield self.build_tool_call_chunk(tc_id, tc.function.name, parsed_input, error_msg)
                            yield self.build_done_chunk("tool_use")
                        else:
                            yield self.build_done_chunk(choice.finish_reason or "stop")
                    except Exception as fallback_err:
                        logger.error(f"Non-streaming fallback failed: {fallback_err}")
                        raise fallback_err
                else:
                    raise stream_err
        except Exception as e:
            logger.error(f"OpenAI API Error: {str(e)}")
            raise e

    def _to_anthropic_messages(self, internal_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anthropic_msgs = []
        current_user_blocks = []
        for msg in internal_messages:
            role = msg["role"]
            if role == "system":
                continue
            if role == "tool":
                current_user_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": msg["tool_call_id"],
                    "content": str(msg["content"])
                })
            elif role == "user":
                if current_user_blocks:
                    anthropic_msgs.append({"role": "user", "content": current_user_blocks})
                    current_user_blocks = []
                anthropic_msgs.append({"role": "user", "content": msg["content"]})
            elif role == "assistant":
                if current_user_blocks:
                    anthropic_msgs.append({"role": "user", "content": current_user_blocks})
                    current_user_blocks = []
                content_blocks = []
                for tb in msg.get("thinking_blocks") or []:
                    tb_type = tb.get("type")
                    if tb_type == "thinking":
                        block = {"type": "thinking", "thinking": tb.get("thinking", "")}
                        if tb.get("signature"):
                            block["signature"] = tb["signature"]
                        content_blocks.append(block)
                    elif tb_type == "redacted_thinking":
                        content_blocks.append({"type": "redacted_thinking", "data": tb.get("data", "")})
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["input"]
                        })
                if content_blocks:
                    anthropic_msgs.append({"role": "assistant", "content": content_blocks})
        if current_user_blocks:
            anthropic_msgs.append({"role": "user", "content": current_user_blocks})
        return anthropic_msgs

    def _to_openai_messages(self, internal_messages: List[Dict[str, Any]], system_prompt: str) -> List[Dict[str, Any]]:
        openai_msgs = []
        if system_prompt:
            openai_msgs.append({"role": "system", "content": system_prompt})
        pending_tool_call_ids = []
        def flush_pending_tools():
            nonlocal pending_tool_call_ids
            while pending_tool_call_ids:
                tc_id = pending_tool_call_ids.pop(0)
                openai_msgs.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": "Tool execution completed."
                })
        for msg in internal_messages:
            role = msg["role"]
            if role == "system":
                continue
            elif role == "user":
                flush_pending_tools()
                openai_msgs.append({"role": "user", "content": msg["content"]})
            elif role == "tool":
                tc_id = msg.get("tool_call_id") or msg.get("id")
                if (not tc_id or tc_id == "legacy_tool") and pending_tool_call_ids:
                    tc_id = pending_tool_call_ids.pop(0)
                elif tc_id and tc_id in pending_tool_call_ids:
                    pending_tool_call_ids.remove(tc_id)
                elif not tc_id:
                    tc_id = "legacy_tool"
                openai_msgs.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": str(msg.get("content", ""))
                })
            elif role == "assistant":
                flush_pending_tools()
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")
                if content is None:
                    content_str = "" if tool_calls else " "
                elif isinstance(content, str):
                    content_str = content
                else:
                    content_str = json.dumps(content)
                item = {
                    "role": "assistant",
                    "content": content_str
                }
                if tool_calls:
                    tcs = []
                    for tc in tool_calls:
                        tc_id = tc.get("id", f"call_{len(tcs)}")
                        pending_tool_call_ids.append(tc_id)
                        tc_item = {
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc.get("name", "unknown"),
                                "arguments": json.dumps(tc.get("input", {})) if isinstance(tc.get("input"), dict) else str(tc.get("input", ""))
                            }
                        }
                        if tc.get("thought_signature"):
                            tc_item["extra_content"] = {
                                "google": {
                                    "thought_signature": tc["thought_signature"]
                                }
                            }
                        tcs.append(tc_item)
                    item["tool_calls"] = tcs
                openai_msgs.append(item)
        flush_pending_tools()
        return openai_msgs
