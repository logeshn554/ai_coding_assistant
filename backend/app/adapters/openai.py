import json
from typing import AsyncGenerator, List, Dict, Any
try:
    from openai import AsyncOpenAI
except ImportError:
    # Stub for environments without the openai package
    class AsyncOpenAI:
        def __init__(self, *args, **kwargs):
            raise ImportError("OpenAI SDK is not installed. Install 'openai' package to use this adapter.")
        async def chat(self, *args, **kwargs):
            raise NotImplementedError("OpenAI SDK not available.")

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
        client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)

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

            response = await client.chat.completions.create(**kwargs)

            tool_calls_accum = {}  # Index -> tool_call data

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
                                "arguments": ""
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

            # Yield completed tool calls after streaming terminates
            for idx, tc in tool_calls_accum.items():
                # Ensure we have a valid ID (Ollama sometimes misses it in some chunks)
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
                    "input": parsed_input
                }

            # Return done with stop reason
            stop_reason = "tool_use" if tool_calls_accum else "stop"
            yield {"type": "done", "stop_reason": stop_reason}

        except Exception as e:
            yield {"type": "text", "content": f"\n[OpenAI API Error: {str(e)}]\n"}
            yield {"type": "done", "stop_reason": "stop"}

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
                    "tool_call_id": msg["tool_call_id"],
                    "content": str(msg["content"])
                })
            elif role == "assistant":
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")
                
                item = {
                    "role": "assistant"
                }
                if content:
                    item["content"] = content
                elif not tool_calls:
                    item["content"] = " "  # OpenAI requires content or tool_calls
                else:
                    item["content"] = None
                
                if tool_calls:
                    tcs = []
                    for tc in tool_calls:
                        tcs.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["input"])
                            }
                        })
                    item["tool_calls"] = tcs
                    
                openai_msgs.append(item)
                
        return openai_msgs
