"""
Agent Loop — Main execution loop for the real coding agent.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_os.providers.model_router import ModelRouter
from agent_os.tools.registry import ToolRegistry


@dataclass
class AgentState:
    """State of the agent execution."""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    step_count: int = 0
    failed: bool = False
    error: Optional[str] = None


class AgentLoop:
    """Main agent execution loop driving recursive LLM reasoning and tool calls."""

    def __init__(
        self,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        max_steps: int = 50,
        max_time_seconds: float = 900.0,
    ) -> None:
        self.model_router = model_router
        self.tool_registry = tool_registry
        self.max_steps = max_steps
        self.max_time_seconds = max_time_seconds

    async def run(self, task: str) -> AgentState:
        """Run the agent loop on a task string."""
        state = AgentState()
        start_time = datetime.now()

        # Add initial user request to message history
        state.messages.append({
            "role": "user",
            "content": task,
        })

        while state.step_count < self.max_steps:
            # Check elapsed time timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > self.max_time_seconds:
                state.failed = True
                state.error = f"Timeout after {elapsed:.0f}s"
                break

            state.step_count += 1

            # Request next action block from LLM
            try:
                # Convert tools to schema
                tool_schemas = self.tool_registry.get_schemas()
                response = await self.model_router.generate(
                    messages=state.messages,
                    tools=tool_schemas if tool_schemas else None,
                )
            except Exception as e:
                state.failed = True
                state.error = f"LLM error: {e}"
                break

            # Append LLM response to messages
            state.messages.append({
                "role": "assistant",
                "content": response.content,
            })

            # Check if LLM indicates turn completion or lacks tool calls
            if not response.tool_calls or response.finish_reason == "end_turn":
                break

            # Execute tool calls synchronously or in parallel
            tool_results = []
            for tool_call in response.tool_calls:
                result = await self.tool_registry.execute(
                    tool_call.name,
                    **tool_call.arguments,
                )
                tool_results.append({
                    "tool_name": tool_call.name,
                    "tool_call_id": tool_call.id,
                    "result": result,
                })

            # Format tool observations back into prompt context
            for tr in tool_results:
                observation = tr["result"].get("output", "")
                if tr["result"].get("error"):
                    observation = f"Error: {tr['result']['error']}"
                
                state.messages.append({
                    "role": "user",
                    "content": f"Tool {tr['tool_name']} returned: {observation}",
                })
                state.tool_results.append(tr)

        if state.step_count >= self.max_steps:
            state.failed = True
            state.error = f"Exceeded max steps ({self.max_steps})"

        return state
