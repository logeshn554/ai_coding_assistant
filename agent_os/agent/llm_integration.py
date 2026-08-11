"""
LLM integration layer for agent reasoning.

Handles:
  - Context building from workspace
  - LLM calls with tool definitions
  - Tool call extraction and parsing
  - Cancellation handling
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from .interfaces import (
    LLMMessage,
    ToolCall,
    ToolDefinition,
    ILLMIntegration,
)


class LLMIntegration(ILLMIntegration):
    """
    Real LLM integration that actually calls an LLM provider.
    """

    def __init__(self, model_router):
        """
        Args:
            model_router: ModelRouter instance for calling LLM providers
        """
        self.model_router = model_router
        self._active_requests: Dict[str, asyncio.Task] = {}

    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: Dict[str, ToolDefinition],
        max_tokens: int = 2000,
    ) -> LLMMessage:
        """
        Call LLM with tools available.

        Args:
            messages: Conversation history
            tools: Available tools to use
            max_tokens: Max tokens for response

        Returns:
            LLMMessage with response and any tool_calls extracted
        """

        # Build tool schemas for LLM
        tool_schemas = self._build_tool_schemas(tools)

        # Build messages in provider format
        provider_messages = self._build_provider_messages(messages)

        # Build system prompt with tool instructions
        system_prompt = self._build_system_prompt(tools)

        # Call LLM
        try:
            response_text = await self.model_router.generate(
                messages=provider_messages,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )

            # Parse response for tool calls and content
            tool_calls, content = self._parse_response(response_text, tools)

            # Return as LLMMessage
            return LLMMessage(
                role="assistant",
                content=content,
                tool_calls=tool_calls,
            )

        except Exception as e:
            # Return error as assistant message
            return LLMMessage(
                role="assistant",
                content=f"Error calling LLM: {str(e)}",
                tool_calls=[],
            )

    async def cancel_request(self, request_id: str) -> None:
        """Cancel an in-flight LLM request."""
        if request_id in self._active_requests:
            task = self._active_requests[request_id]
            task.cancel()
            del self._active_requests[request_id]

    def _build_tool_schemas(self, tools: Dict[str, ToolDefinition]) -> List[Dict]:
        """Convert tool definitions to LLM tool schema format."""
        schemas = []
        for name, tool_def in tools.items():
            schema = {
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": tool_def.input_schema,
                },
            }
            schemas.append(schema)
        return schemas

    def _build_provider_messages(self, messages: List[LLMMessage]) -> List[Dict[str, str]]:
        """Convert LLMMessages to provider message format."""
        provider_messages = []

        for msg in messages:
            if msg.role == "system":
                provider_messages.append({"role": "system", "content": msg.content})
            elif msg.role == "assistant":
                provider_messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == "user":
                content = msg.content

                # Append tool results if any
                if msg.tool_results:
                    tool_results_text = self._format_tool_results(msg.tool_results)
                    content += f"\n\n{tool_results_text}"

                provider_messages.append({"role": "user", "content": content})

        return provider_messages

    def _build_system_prompt(self, tools: Dict[str, ToolDefinition]) -> str:
        """Build system prompt with tool descriptions."""
        tool_list = "\n".join(
            [
                f"- {t.name}: {t.description} (timeout: {t.timeout_seconds}s)"
                for t in tools.values()
            ]
        )

        return f"""You are an AI coding assistant with access to the following tools:

{tool_list}

When you need to perform an action, use a tool by responding with JSON in this format:
{{"tool_calls": [{{"tool_name": "tool_name", "arguments": {{...}}}}]}}

After using a tool, you will receive the results and can continue reasoning.
Continue using tools until the task is complete, then provide a final summary.

Remember:
- Only use tools that are available
- Check tool results carefully before proceeding
- If a tool fails, try alternative approaches
- Always verify your work before claiming completion"""

    def _parse_response(
        self, response_text: str, tools: Dict[str, ToolDefinition]
    ) -> tuple[List[ToolCall], str]:
        """
        Parse LLM response to extract tool calls and content.

        Looks for JSON tool call blocks or tool use patterns.
        """
        tool_calls = []
        content = response_text

        # Pattern 1: JSON block with tool_calls
        json_pattern = r"\{\"tool_calls\": \[(.*?)\]\}"
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        if matches:
            try:
                json_text = "{\"tool_calls\": [" + matches[0] + "]}"
                data = json.loads(json_text)
                for call_data in data.get("tool_calls", []):
                    tool_call = self._parse_tool_call(call_data, tools)
                    if tool_call:
                        tool_calls.append(tool_call)
                # Remove JSON from content
                content = re.sub(json_pattern, "", response_text, flags=re.DOTALL)
            except json.JSONDecodeError:
                pass

        # Pattern 2: Individual function call markers
        func_pattern = r"<tool_call>(.*?)</tool_call>"
        matches = re.findall(func_pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                call_data = json.loads(match)
                tool_call = self._parse_tool_call(call_data, tools)
                if tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                pass

        return tool_calls, content.strip()

    def _parse_tool_call(
        self, call_data: Dict[str, Any], tools: Dict[str, ToolDefinition]
    ) -> Optional[ToolCall]:
        """Parse a single tool call from LLM response."""
        tool_name = call_data.get("tool_name") or call_data.get("name")
        arguments = call_data.get("arguments") or call_data.get("args") or {}

        if not tool_name or tool_name not in tools:
            return None

        import uuid
        import time

        return ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            tool_call_id=str(uuid.uuid4()),
            timestamp=time.time(),
        )

    def _format_tool_results(self, tool_results) -> str:
        """Format tool results for inclusion in next LLM message."""
        lines = ["Tool Results:"]
        for result in tool_results:
            lines.append(f"  - {result.tool_name}: {result.status}")
            if result.result:
                lines.append(f"    Result: {result.result}")
            if result.error:
                lines.append(f"    Error: {result.error}")
        return "\n".join(lines)
