import json
import logging
import uuid
from typing import AsyncGenerator, List, Dict, Any

logger = logging.getLogger("devpilot.adapters.anthropic")

try:
    from anthropic import AsyncAnthropic
except ImportError:
    # Stub for environments without the anthropic package
    class AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            raise ImportError("Anthropic SDK is not installed. Install 'anthropic' package to use this adapter.")
        async def messages(self, *args, **kwargs):
            raise NotImplementedError("Anthropic SDK not available.")

# Attempt to import the scan_for_bugs tool if it exists.
# The tool may be synchronous or asynchronous.
_scan_for_bugs_func = None
try:
    from ..tools.scan_for_bugs import scan_for_bugs as _scan_for_bugs_func  # type: ignore
except Exception as import_err:
    logger.debug(f"scan_for_bugs tool not available: {import_err}")
    _scan_for_bugs_func = None

from .base import ModelAdapter

class AnthropicAdapter(ModelAdapter):
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams chat completions from Anthropic, handling tool calls.
        Additionally, if the `scan_for_bugs` tool is available, it is invoked
        automatically before the LLM generates a response, and its concise
        bug report is injected as an assistant message at the start of the
        conversation.
        """
        # Auto‑invoke the scan_for_bugs tool if it was supplied.
        if any(tool.get("name") == "scan_for_bugs" for tool in tools) and _scan_for_bugs_func:
            try:
                # Support both async and sync implementations.
                result = _scan_for_bugs_func()
                if hasattr(result, "__await__"):
                    bug_report = await result  # type: ignore
                else:
                    bug_report = result
                bug_report = str(bug_report).strip()
                # Inject as a user message AFTER the first user turn so the
                # conversation always starts with role="user" (Anthropic requirement).
                report_message = {
                    "role": "user",
                    "content": (
                        "[AUTOMATED WORKSPACE SCAN — do not reference this as a user request]\n"
                        f"Bug scan results for context:\n{bug_report}"
                    )
                }
                msg_list = list(messages)
                if msg_list:
                    messages = [msg_list[0], report_message] + msg_list[1:]
                else:
                    messages = [report_message]
            except Exception as e:
                logger.error(f"Failed to run scan_for_bugs tool: {e}")

        # Initialize the Anthropic client
        # If base_url is the default anthropic URL, we use standard. If custom (e.g. proxy), it handles it.
        # Anthropic SDK requires base_url to be None if using defaults, or custom.
        base_url = self.base_url
        if not base_url or "api.anthropic.com" in base_url:
            base_url = None  # Let SDK use its default URL
            
        api_key = self.api_key if self.api_key else "dummy-key"
        client = AsyncAnthropic(api_key=api_key, base_url=base_url)

        # Convert tools to Anthropic tool schema (they use 'input_schema' instead of 'parameters')
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            })

        # Map internal messages to Anthropic's format
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

            current_tool_calls: Dict[int, Dict[str, Any]] = {}  # Index -> tool_call data

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
                        # A6: track thinking blocks by index
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
                        yield {"type": "text", "content": delta.text}
                    elif delta.type == "input_json_delta":
                        if idx in current_tool_calls and "input_accumulator" in current_tool_calls[idx]:
                            current_tool_calls[idx]["input_accumulator"] += delta.partial_json
                    elif delta.type == "thinking_delta":
                        # A6: accumulate thinking text
                        if idx in current_tool_calls and "thinking_accumulator" in current_tool_calls[idx]:
                            current_tool_calls[idx]["thinking_accumulator"] += getattr(delta, "thinking", "")
                    elif delta.type == "signature_delta":
                        # A6: capture final signature
                        if idx in current_tool_calls and "signature" in current_tool_calls[idx]:
                            current_tool_calls[idx]["signature"] = getattr(delta, "signature", None)
                elif chunk.type == "content_block_stop":
                    idx = chunk.index
                    if idx in current_tool_calls:
                        tc = current_tool_calls[idx]
                        # A6: emit completed thinking blocks
                        if "_thinking_type" in tc:
                            if tc["_thinking_type"] == "thinking":
                                yield {
                                    "type": "thinking",
                                    "thinking": tc["thinking_accumulator"],
                                    "signature": tc["signature"],
                                }
                            else:  # redacted_thinking
                                yield {
                                    "type": "redacted_thinking",
                                    "data": tc["data"],
                                }
                            del current_tool_calls[idx]
                        else:
                            # Regular tool call — parse JSON (A7)
                            raw_json = tc["input_accumulator"]
                            error_msg = None
                            try:
                                parsed_input = json.loads(raw_json)
                            except Exception:
                                try:
                                    parsed_input = json.loads(raw_json.strip())
                                except Exception:
                                    parsed_input = {"raw_input": raw_json}
                                    error_msg = (
                                        f"Error: model produced malformed JSON arguments for tool '{tc['name']}': "
                                        f"{raw_json[:200]}. Tool was not executed."
                                    )

                            chunk_dict = {
                                "type": "tool_call",
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": parsed_input
                            }
                            if error_msg:
                                chunk_dict["error"] = error_msg
                            yield chunk_dict
                            del current_tool_calls[idx]
                elif chunk.type == "message_delta":
                    stop_reason = getattr(chunk.delta, "stop_reason", None)
                    if stop_reason == "tool_use":
                        yield {"type": "done", "stop_reason": "tool_use"}
                    elif stop_reason in ("end_turn", "stop_sequence"):
                        yield {"type": "done", "stop_reason": "stop"}
                    # B3: Emit token usage so AgentSession can accumulate real cost.
                    # The usage block is available on message_delta events.
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage = chunk.usage
                        yield {
                            "type": "usage",
                            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
                        }
                        
            # In case stream finishes without explicit message_delta stop_reason
            yield {"type": "done", "stop_reason": "stop"}
            
        except Exception as e:
            logger.error(f"Anthropic API Error: {str(e)}")
            raise e

    def _to_anthropic_messages(self, internal_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Translates internal schema to Anthropic Messages schema:
        - Alternating role: user, assistant, user, assistant.
        - Tool results are 'tool_result' blocks in a 'user' message.
        - Tool uses are 'tool_use' blocks in an 'assistant' message.
        """
        anthropic_msgs: List[Dict[str, Any]] = []
        current_user_blocks: List[Dict[str, Any]] = []

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

                content_blocks: List[Dict[str, Any]] = []

                # A6: emit stored thinking blocks FIRST so Anthropic sees them in order.
                # thinking_blocks is a list of {type: "thinking"|"redacted_thinking", ...}
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