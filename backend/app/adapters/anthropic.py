import json
from typing import AsyncGenerator, List, Dict, Any
try:
    from anthropic import AsyncAnthropic
except ImportError:
    # Stub for environments without the anthropic package
    class AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            raise ImportError("Anthropic SDK is not installed. Install 'anthropic' package to use this adapter.")
        async def messages(self, *args, **kwargs):
            raise NotImplementedError("Anthropic SDK not available.")

from .base import ModelAdapter

class AnthropicAdapter(ModelAdapter):
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Initialize the Anthropic client
        # If base_url is the default anthropic URL, we use standard. If custom (e.g. proxy), it handles it.
        # Anthropic SDK requires base_url to be None if using defaults, or custom.
        base_url = self.base_url
        if not base_url or "api.anthropic.com" in base_url:
            base_url = None # Let SDK use its default URL
            
        client = AsyncAnthropic(api_key=self.api_key, base_url=base_url)

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

        try:
            stream = await client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                system=system_prompt,
                messages=anthropic_messages,
                tools=anthropic_tools,
                stream=True
            )

            current_tool_calls = {}  # Index -> tool_call data

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
                elif chunk.type == "content_block_delta":
                    idx = chunk.index
                    delta = chunk.delta
                    if delta.type == "text_delta":
                        yield {"type": "text", "content": delta.text}
                    elif delta.type == "input_json_delta":
                        if idx in current_tool_calls:
                            current_tool_calls[idx]["input_accumulator"] += delta.partial_json
                elif chunk.type == "content_block_stop":
                    idx = chunk.index
                    if idx in current_tool_calls:
                        tc = current_tool_calls[idx]
                        try:
                            # Attempt to parse accumulated arguments
                            parsed_input = json.loads(tc["input_accumulator"])
                        except Exception:
                            # If parsing fails, fall back to empty or try to clean up
                            try:
                                # Sometimes LLMs yield unescaped control chars, try to clean
                                cleaned = tc["input_accumulator"].strip()
                                parsed_input = json.loads(cleaned)
                            except Exception:
                                parsed_input = {"raw_input": tc["input_accumulator"]}
                        
                        yield {
                            "type": "tool_call",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": parsed_input
                        }
                        del current_tool_calls[idx]
                elif chunk.type == "message_delta":
                    stop_reason = getattr(chunk.delta, "stop_reason", None)
                    if stop_reason == "tool_use":
                        yield {"type": "done", "stop_reason": "tool_use"}
                    elif stop_reason in ("end_turn", "stop_sequence"):
                        yield {"type": "done", "stop_reason": "stop"}
                        
            # In case stream finishes without explicit message_delta stop_reason
            yield {"type": "done", "stop_reason": "stop"}
            
        except Exception as e:
            yield {"type": "text", "content": f"\n[Anthropic API Error: {str(e)}]\n"}
            yield {"type": "done", "stop_reason": "stop"}

    def _to_anthropic_messages(self, internal_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Translates internal schema to Anthropic Messages schema:
        - Alternating role: user, assistant, user, assistant.
        - Tool results are 'tool_result' blocks in a 'user' message.
        - Tool uses are 'tool_use' blocks in an 'assistant' message.
        """
        anthropic_msgs = []
        current_user_blocks = []

        for msg in internal_messages:
            role = msg["role"]
            
            if role == "system":
                # System instructions are passed separately
                continue
                
            if role == "tool":
                # Tool result
                current_user_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": msg["tool_call_id"],
                    "content": str(msg["content"])
                })
                
            elif role == "user":
                # Flush accumulated tool results first if we hit a user message
                if current_user_blocks:
                    anthropic_msgs.append({"role": "user", "content": current_user_blocks})
                    current_user_blocks = []
                
                anthropic_msgs.append({"role": "user", "content": msg["content"]})
                
            elif role == "assistant":
                # Flush accumulated tool results first if we hit an assistant message
                if current_user_blocks:
                    anthropic_msgs.append({"role": "user", "content": current_user_blocks})
                    current_user_blocks = []
                
                content_blocks = []
                # Include text content if present
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                
                # Include any tool calls
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["input"]
                        })
                
                # A assistant message must contain at least one content block
                if content_blocks:
                    anthropic_msgs.append({"role": "assistant", "content": content_blocks})

        # Final flush for any remaining tool results
        if current_user_blocks:
            anthropic_msgs.append({"role": "user", "content": current_user_blocks})

        return anthropic_msgs
