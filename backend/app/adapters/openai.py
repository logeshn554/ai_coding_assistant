import json
import logging
import asyncio
import os
from typing import AsyncGenerator, List, Dict, Any

logger = logging.getLogger("devpilot.adapters.openai")

try:
    from openai import AsyncOpenAI
except ImportError:
    # Stub for environments without the openai package
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            raise ImportError("OpenAI SDK is not installed. Install 'openai' package to use this adapter.")
        async def chat(self, *args, **kwargs):
            raise NotImplementedError("OpenAI SDK not available.")

# Attempt to import the scan_for_bugs tool; if unavailable, define a placeholder.
try:
    from ..tools import scan_for_bugs_sync as scan_for_bugs  # Adjust relative import as needed
except Exception:
    def scan_for_bugs(root_path: str) -> Dict[str, Any]:
        """Placeholder implementation if the real tool is not available."""
        return {"error": "scan_for_bugs tool not found"}

from .base import ModelAdapter

class OpenAIAdapter(ModelAdapter):
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Initialize AsyncOpenAI client
        # This will automatically pick up base_url and api_key
        base_url = self.base_url if self.base_url else None
        api_key = self.api_key if self.api_key else "dummy-key"
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Convert tools to OpenAI format
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

        # Translate internal messages to OpenAI message format
        openai_messages = self._to_openai_messages(messages, system_prompt)

        try:
            kwargs = {
                "model": self.model_name,
                "messages": openai_messages,
                "stream": True
            }
            if openai_tools:
                kwargs["tools"] = openai_tools

            tool_calls_accum = {}  # Index -> tool_call data

            try:
                response = await client.chat.completions.create(**kwargs)

                async for chunk in response:
                    if not chunk.choices:
                        continue
                    
                    delta = chunk.choices[0].delta
                    
                    # Check for content delta
                    if getattr(delta, "content", None) is not None:
                        yield {"type": "text", "content": delta.content}
                    
                    # Check for tool call delta
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
                            
                            # Populate ID
                            if getattr(tc_chunk, "id", None) is not None:
                                tool_calls_accum[idx]["id"] = tc_chunk.id
                            # Populate Name
                            if getattr(tc_chunk, "function", None) is not None:
                                func = tc_chunk.function
                                if getattr(func, "name", None) is not None:
                                    tool_calls_accum[idx]["name"] = func.name
                                if getattr(func, "arguments", None) is not None:
                                    tool_calls_accum[idx]["arguments"] += func.arguments
                                    
                            # Extract thought signature if present (Gemini)
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

                # Yield completed tool calls after streaming terminates
                for idx, tc in tool_calls_accum.items():
                    tc_id = tc["id"] or f"call_{idx}"
                    tc_name = tc["name"]
                    tc_args = tc["arguments"]
                    
                    try:
                        parsed_input = json.loads(tc_args)
                    except Exception:
                        try:
                            parsed_input = json.loads(tc_args.strip())
                        except Exception:
                            parsed_input = {"raw_input": tc_args}
                            
                    yield {
                        "type": "tool_call",
                        "id": tc_id,
                        "name": tc_name,
                        "input": parsed_input,
                        "thought_signature": tc.get("thought_signature")
                    }

                stop_reason = "tool_use" if tool_calls_accum else "stop"
                yield {"type": "done", "stop_reason": stop_reason}

            except Exception as stream_err:
                # If streaming fails (e.g. Bedrock/LiteLLM nova-micro tool use stream error),
                # fallback to non-streaming request if tools were provided.
                if openai_tools:
                    logger.warning(f"Streaming failed with tools ({stream_err}), falling back to non-streaming request.")
                    kwargs["stream"] = False
                    non_stream_resp = await client.chat.completions.create(**kwargs)
                    if not non_stream_resp.choices:
                        yield {"type": "done", "stop_reason": "stop"}
                        return

                    choice = non_stream_resp.choices[0]
                    msg = choice.message
                    if getattr(msg, "content", None):
                        yield {"type": "text", "content": msg.content}
                    
                    tcs = getattr(msg, "tool_calls", None)
                    if tcs:
                        for idx, tc in enumerate(tcs):
                            tc_id = tc.id or f"call_{idx}"
                            tc_name = tc.function.name
                            tc_args = tc.function.arguments
                            try:
                                parsed_input = json.loads(tc_args)
                            except Exception:
                                parsed_input = {"raw_input": tc_args}
                            yield {
                                "type": "tool_call",
                                "id": tc_id,
                                "name": tc_name,
                                "input": parsed_input,
                                "thought_signature": None
                            }
                        yield {"type": "done", "stop_reason": "tool_use"}
                    else:
                        yield {"type": "done", "stop_reason": choice.finish_reason or "stop"}
                else:
                    raise stream_err

        except Exception as e:
            logger.error(f"OpenAI API Error: {str(e)}")
            raise e

    def _to_openai_messages(self, internal_messages: List[Dict[str, Any]], system_prompt: str) -> List[Dict[str, Any]]:
        """
        Translates internal schema to OpenAI Chat Completions schema.
        We prepend the system prompt as the first message.
        """
        openai_msgs = []
        
        # Add system prompt first
        if system_prompt:
            openai_msgs.append({"role": "system", "content": system_prompt})
            
        for msg in internal_messages:
            role = msg["role"]
            
            if role == "system":
                # System prompt is handled separately or is already prepended
                continue
            elif role == "user":
                openai_msgs.append({"role": "user", "content": msg["content"]})
            elif role == "tool":
                openai_msgs.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", "legacy_tool"),
                    "content": str(msg.get("content", ""))
                })
            elif role == "assistant":
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")

                # Ensure content is always a plain string
                if content is None:
                    content_str = "" if tool_calls else " "
                elif isinstance(content, str):
                    content_str = content
                else:
                    # Dicts/lists/ints from legacy DB: stringify them
                    content_str = json.dumps(content)

                item = {
                    "role": "assistant",
                    "content": content_str
                }

                if tool_calls:
                    tcs = []
                    for tc in tool_calls:
                        tc_item = {
                            "id": tc.get("id", f"call_{len(tcs)}"),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", "unknown"),
                                "arguments": json.dumps(tc.get("input", {}))
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
                
        return openai_msgs

    async def generate_bug_report(self) -> str:
        """
        Scans the entire workspace for bugs using the `scan_for_bugs` tool and returns a concise report.
        The report is serialized as JSON and truncated to a reasonable length if necessary.
        """
        try:
            loop = asyncio.get_event_loop()
            # Assume `scan_for_bugs` is a synchronous function that returns a dict-like structure.
            bug_data = await loop.run_in_executor(None, scan_for_bugs, os.getcwd())
        except Exception as e:
            logger.error(f"Failed to execute scan_for_bugs: {e}")
            raise

        try:
            report = json.dumps(bug_data, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to serialize bug data to JSON: {e}")
            raise

        # Truncate overly long reports to keep the output concise
        max_length = 2000  # characters
        if len(report) > max_length:
            report = report[: max_length - 3] + "..."

        return report