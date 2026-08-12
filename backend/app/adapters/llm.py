import json
import logging
import asyncio
import os
import httpx
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

_anthropic_clients: dict = {}
_openai_clients: dict = {}

def _get_anthropic_client(api_key: str, base_url: Optional[str] = None, timeout: float = 180.0):
    key = (api_key, base_url, timeout)
    if key not in _anthropic_clients:
        _anthropic_clients[key] = AsyncAnthropic(api_key=api_key, base_url=base_url, timeout=timeout)
    return _anthropic_clients[key]

def _get_openai_client(api_key: str, base_url: Optional[str] = None, timeout: float = 180.0):
    key = (api_key, base_url, timeout)
    if key not in _openai_clients:
        _openai_clients[key] = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return _openai_clients[key]


import time

class _RpmLimiter:
    def __init__(self):
        self.history = []
        self.lock = asyncio.Lock()

    def get_limit(self) -> int:
        from ..state import config_manager
        env_limit = os.environ.get("DEVPILOT_RPM")
        if env_limit:
            try:
                return int(env_limit)
            except ValueError:
                pass
        try:
            return config_manager.get_devpilot_rpm()
        except Exception:
            return 15

    async def acquire(self):
        async with self.lock:
            while True:
                now = time.time()
                limit = self.get_limit()
                # Remove timestamps older than 60 seconds
                self.history = [t for t in self.history if now - t < 60.0]
                if len(self.history) < limit:
                    self.history.append(now)
                    break
                # Wait until the oldest request in the window falls out of the window
                sleep_time = 60.0 - (now - self.history[0])
                if sleep_time > 0:
                    logger.info(f"RPM limit ({limit}) reached. Sleeping for {sleep_time:.2f}s...")
                    await asyncio.sleep(sleep_time)


class LLMAdapter(ModelAdapter):
    """
    Unified LLM adapter for both Anthropic and OpenAI.
    Provider-specific behaviors are routed internally based on self.provider.
    """
    _rpm_limiter = None

    def __init__(self, api_key: str, base_url: str, model_name: str, provider: str):
        super().__init__(api_key, base_url, model_name)
        self.provider = provider

    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Lazily initialize global RPM limiter
        if LLMAdapter._rpm_limiter is None:
            LLMAdapter._rpm_limiter = _RpmLimiter()

        # Bug scanning was previously auto-injected here on every LLM call.
        # Removed: scanning is now only triggered when the scan_for_bugs tool
        # is explicitly called by the model, avoiding context pollution.

        # Acquire rate limiter ticket before calling LLM providers
        await LLMAdapter._rpm_limiter.acquire()

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
        timeout_val = float(os.environ.get("DEVPILOT_STREAMING_TIMEOUT") or os.environ.get("ANTHROPIC_TIMEOUT") or "180.0")
        client = _get_anthropic_client(api_key, base_url, timeout_val)

        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            })

        anthropic_messages = self._to_anthropic_messages(messages)
        from ..state import config_manager
        temp_setting = config_manager.get_temperature()
        top_p_setting = config_manager.get_top_p()
        max_tokens_setting = config_manager.get_max_tokens()
        stream_setting = config_manager.get_stream()

        is_agent_mode = "OPERATING MODE: Agent" in system_prompt or "MULTI-AGENT ORCHESTRATION" in system_prompt
        profile = config_manager.get_active_profile()
        _supports_thinking = profile.get("supports_thinking")
        if _supports_thinking is None:
            _model_lower = self.model_name.lower()
            _supports_thinking = (
                "claude-3-7" in _model_lower or
                ("claude" in _model_lower and "opus-4" in _model_lower)
            )
        try:
            kwargs = {
                "model": self.model_name,
                "system": system_prompt,
                "messages": anthropic_messages,
                "tools": anthropic_tools,
                "stream": stream_setting,
                "temperature": temp_setting,
                "top_p": top_p_setting,
                "max_tokens": max_tokens_setting,
            }
            if is_agent_mode:
                if _supports_thinking:
                    kwargs["max_tokens"] = max(max_tokens_setting, 16000)
                    kwargs["thinking"] = {
                        "type": "enabled",
                        "budget_tokens": min(16000, kwargs["max_tokens"] - 2000)
                    }
                    kwargs.pop("temperature", None)
                    kwargs.pop("top_p", None)
                else:
                    kwargs["max_tokens"] = max_tokens_setting
            else:
                kwargs["max_tokens"] = max_tokens_setting


            if not stream_setting:
                response = await client.messages.create(**kwargs)
                if hasattr(response, "usage") and response.usage:
                    yield self.build_usage_chunk(
                        getattr(response.usage, "input_tokens", 0),
                        getattr(response.usage, "output_tokens", 0),
                        self.model_name
                    )
                for block in response.content:
                    if block.type == "text":
                        yield self.build_text_chunk(block.text)
                    elif block.type == "tool_use":
                        parsed_input, error_msg = self.parse_tool_arguments(block.name, json.dumps(block.input))
                        yield self.build_tool_call_chunk(block.id, block.name, parsed_input, error_msg)
                
                stop_reason = response.stop_reason
                if stop_reason == "tool_use":
                    yield self.build_done_chunk("tool_use")
                else:
                    yield self.build_done_chunk("stop")
                return

            stream = await client.messages.create(**kwargs)
            current_tool_calls = {}

            async for chunk in stream:
                if chunk.type == "message_start":
                    if hasattr(chunk, "message") and hasattr(chunk.message, "usage") and chunk.message.usage:
                        usage = chunk.message.usage
                        yield self.build_usage_chunk(
                            getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0), self.model_name
                        )
                elif chunk.type == "content_block_start":
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
                            getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0), self.model_name
                        )
            yield self.build_done_chunk("stop")
        except Exception as e:
            err_str = str(e).lower()
            is_timeout = False
            if isinstance(e, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
                is_timeout = True
            elif "timeout" in err_str or "timed out" in err_str or "connecttimeout" in err_str:
                is_timeout = True

            if is_timeout:
                logger.error(f"Anthropic API request timed out ({e})")
                raise TimeoutError(f"Request timed out connecting to provider ({base_url or 'Anthropic API'}). Please check network or model endpoint.") from e

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
        timeout_val = float(os.environ.get("DEVPILOT_STREAMING_TIMEOUT") or os.environ.get("OPENAI_TIMEOUT") or "180.0")
        client = _get_openai_client(api_key, base_url, timeout_val)

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
        from ..state import config_manager
        temp_setting = config_manager.get_temperature()
        top_p_setting = config_manager.get_top_p()
        max_tokens_setting = config_manager.get_max_tokens()
        seed_setting = config_manager.get_seed()
        stream_setting = config_manager.get_stream()

        try:
            kwargs = {
                "model": self.model_name,
                "messages": openai_messages,
                "temperature": temp_setting,
                "top_p": top_p_setting,
                "max_tokens": max_tokens_setting,
            }
            if seed_setting is not None:
                kwargs["seed"] = seed_setting
            if openai_tools:
                kwargs["tools"] = openai_tools

            if not stream_setting:
                kwargs["stream"] = False
                response = await client.chat.completions.create(**kwargs)
                if hasattr(response, "usage") and response.usage:
                    yield self.build_usage_chunk(
                        getattr(response.usage, "prompt_tokens", 0),
                        getattr(response.usage, "completion_tokens", 0),
                        self.model_name
                    )
                if response.choices:
                    choice = response.choices[0]
                    if getattr(choice.message, "content", None) is not None:
                        yield self.build_text_chunk(choice.message.content)
                    tcs = getattr(choice.message, "tool_calls", None)
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
                else:
                    yield self.build_done_chunk("stop")
                return

            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
            tool_calls_accum = {}
            try:
                response = await client.chat.completions.create(**kwargs)
                async for chunk in response:
                    if hasattr(chunk, "usage") and chunk.usage:
                        yield self.build_usage_chunk(
                            getattr(chunk.usage, "prompt_tokens", 0),
                            getattr(chunk.usage, "completion_tokens", 0),
                            self.model_name
                        )
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
                is_timeout = False
                if isinstance(stream_err, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
                    is_timeout = True
                elif "timeout" in err_str or "timed out" in err_str or "connecttimeout" in err_str:
                    is_timeout = True

                if is_timeout:
                    logger.error(f"OpenAI API request timed out ({stream_err})")
                    raise TimeoutError(f"Request timed out connecting to provider ({base_url or 'OpenAI API'}). Please check network or model endpoint.") from stream_err

                if openai_tools:
                    logger.warning(f"Streaming failed with tools ({stream_err}), falling back to non-streaming request.")
                    kwargs["stream"] = False
                    try:
                        non_stream_resp = await client.chat.completions.create(**kwargs)
                        if hasattr(non_stream_resp, "usage") and non_stream_resp.usage:
                            yield self.build_usage_chunk(
                                getattr(non_stream_resp.usage, "prompt_tokens", 0),
                                getattr(non_stream_resp.usage, "completion_tokens", 0),
                                self.model_name
                            )
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
        
        from ..state import config_manager
        profile = config_manager.get_active_profile()
        _supports_thinking = profile.get("supports_thinking")
        if _supports_thinking is None:
            _model_lower = self.model_name.lower()
            _supports_thinking = (
                "claude-3-7" in _model_lower or
                ("claude" in _model_lower and "opus-4" in _model_lower)
            )

        def flush_user_blocks():
            if not current_user_blocks:
                return
            if len(current_user_blocks) == 1 and current_user_blocks[0]["type"] == "text":
                anthropic_msgs.append({"role": "user", "content": current_user_blocks[0]["text"]})
            else:
                anthropic_msgs.append({"role": "user", "content": list(current_user_blocks)})
            current_user_blocks.clear()

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
                content = msg["content"]
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                try:
                                    header, b64_data = url.split(";base64,", 1)
                                    media_type = header.replace("data:", "")
                                    current_user_blocks.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": b64_data
                                        }
                                    })
                                except Exception:
                                    current_user_blocks.append({"type": "text", "text": f"[Image: {url[:60]}]"})
                            else:
                                current_user_blocks.append({"type": "text", "text": f"[Image URL: {url}]"})
                        elif isinstance(item, dict):
                            current_user_blocks.append(item)
                        else:
                            current_user_blocks.append({"type": "text", "text": str(item)})
                else:
                    current_user_blocks.append({
                        "type": "text",
                        "text": str(content)
                    })
            elif role == "assistant":
                flush_user_blocks()
                
                content_blocks = []
                if _supports_thinking:
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
                    if anthropic_msgs and anthropic_msgs[-1]["role"] == "assistant":
                        anthropic_msgs[-1]["content"].extend(content_blocks)
                    else:
                        anthropic_msgs.append({"role": "assistant", "content": content_blocks})
        
        flush_user_blocks()
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
                content = msg["content"]
                if isinstance(content, list):
                    formatted_user_content = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "image":
                            source = item.get("source", {})
                            b64_data = source.get("data", "")
                            media_type = source.get("media_type", "image/png")
                            formatted_user_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64_data}"}
                            })
                        elif isinstance(item, dict):
                            formatted_user_content.append(item)
                        else:
                            formatted_user_content.append({"type": "text", "text": str(item)})
                    openai_msgs.append({"role": "user", "content": formatted_user_content})
                else:
                    openai_msgs.append({"role": "user", "content": content})

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
