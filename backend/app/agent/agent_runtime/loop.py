"""
Agent Loop — The core LLM ↔ Tool execution cycle.

This replaces the simulated ``Conversation.stream()`` with a real reasoning
loop that calls an actual LLM, parses tool calls, executes tools, observes
results, and continues until the agent reaches a conclusion.

The loop implements:
    LLM → tool_call → execute_tool → observe_result → LLM → ... → final_answer
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

from agent_runtime.llm import LLMProvider, LLMResponse, Message, ToolCallRequest
from agent_runtime.tools import ToolRegistry, ToolResult

logger = logging.getLogger("agent_runtime.loop")


@dataclass
class AgentEvent:
    """Observable event emitted during the agent loop."""
    type: str  # "llm_call", "tool_call", "tool_result", "final", "error"
    content: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_result: Optional[str] = None
    cost_usd: float = 0.0
    tokens: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class LoopConfig:
    """Configuration for the agent loop."""
    max_iterations: int = 25
    max_tool_calls: int = 50
    max_cost_usd: float = 5.0
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class LoopResult:
    """Final result of the agent loop."""
    success: bool
    output: str
    iterations: int = 0
    total_tool_calls: int = 0
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    events: list[AgentEvent] = field(default_factory=list)
    error: Optional[str] = None


async def agent_loop(
    llm: LLMProvider,
    tool_registry: ToolRegistry,
    system_prompt: str,
    user_message: str,
    config: LoopConfig | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    """Run the agent reasoning loop, yielding events as they occur.

    This is the core execution cycle. It:
    1. Sends messages to the LLM with available tool definitions.
    2. If the LLM returns tool calls, executes them and appends observations.
    3. If the LLM returns a final text response, yields it and stops.
    4. Enforces iteration, tool call, and cost limits.

    Args:
        llm: The LLM provider to use for generation.
        tool_registry: Registry of available tools.
        system_prompt: System instructions for the agent.
        user_message: The user's task description.
        config: Loop configuration (limits, temperature, etc.).

    Yields:
        AgentEvent objects for each step of the loop.
    """
    if config is None:
        config = LoopConfig()

    # Build initial messages
    messages: list[Message] = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=user_message),
    ]

    # Get tool schemas for the LLM
    tool_schemas = tool_registry.get_llm_schemas()

    total_cost = 0.0
    total_tool_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for iteration in range(1, config.max_iterations + 1):
        logger.info("Agent loop iteration %d/%d", iteration, config.max_iterations)

        # 1. Call the LLM
        try:
            response = await llm.generate(
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
        except Exception as e:
            logger.error("LLM call failed on iteration %d: %s", iteration, e)
            yield AgentEvent(
                type="error",
                content=f"LLM call failed: {type(e).__name__}: {e}",
            )
            return

        total_cost += response.cost_usd
        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens

        yield AgentEvent(
            type="llm_call",
            content=response.content,
            cost_usd=response.cost_usd,
            tokens=response.input_tokens + response.output_tokens,
        )

        # 2. Check cost limit
        if total_cost > config.max_cost_usd:
            logger.warning("Cost limit exceeded: $%.4f > $%.4f", total_cost, config.max_cost_usd)
            yield AgentEvent(
                type="error",
                content=f"Cost limit exceeded: ${total_cost:.4f} > ${config.max_cost_usd:.4f}",
            )
            return

        # 3. If the LLM returned a final response (no tool calls), we're done
        if response.is_final:
            logger.info("Agent reached final response on iteration %d", iteration)
            yield AgentEvent(
                type="final",
                content=response.content,
                cost_usd=total_cost,
                tokens=total_input_tokens + total_output_tokens,
            )
            return

        # 4. Process tool calls
        if response.has_tool_calls:
            # Append assistant message with tool calls to history
            messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            for tool_call in response.tool_calls:
                total_tool_calls += 1

                if total_tool_calls > config.max_tool_calls:
                    logger.warning("Tool call limit exceeded: %d", total_tool_calls)
                    yield AgentEvent(
                        type="error",
                        content=f"Tool call limit exceeded: {total_tool_calls} > {config.max_tool_calls}",
                    )
                    return

                yield AgentEvent(
                    type="tool_call",
                    tool_name=tool_call.name,
                    tool_args=tool_call.arguments,
                )

                # Execute the tool
                result = await tool_registry.execute(tool_call.name, tool_call.arguments)

                # Format result for the LLM
                if result.success:
                    result_text = result.output
                else:
                    result_text = f"Error: {result.error}" if result.error else "Tool execution failed"

                yield AgentEvent(
                    type="tool_result",
                    tool_name=tool_call.name,
                    tool_result=result_text[:10_000],  # Cap observation length
                )

                # Append tool result to message history
                messages.append(Message(
                    role="tool",
                    content=result_text[:10_000],
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                ))

            # Continue the loop — LLM will see the tool results
            continue

        # 5. If we get here, the LLM returned content but the finish_reason isn't "stop"
        # This can happen with "length" truncation — treat as final
        logger.warning("Unexpected finish_reason '%s' on iteration %d", response.finish_reason, iteration)
        yield AgentEvent(
            type="final",
            content=response.content or "Agent finished without a clear conclusion.",
            cost_usd=total_cost,
        )
        return

    # Max iterations reached
    logger.warning("Agent loop exhausted max iterations (%d)", config.max_iterations)
    yield AgentEvent(
        type="error",
        content=f"Agent loop exhausted maximum iterations ({config.max_iterations})",
    )


async def run_agent(
    llm: LLMProvider,
    tool_registry: ToolRegistry,
    system_prompt: str,
    user_message: str,
    config: LoopConfig | None = None,
) -> LoopResult:
    """Convenience wrapper that collects all events and returns a LoopResult.

    Use ``agent_loop()`` directly if you need to stream events in real-time.
    """
    if config is None:
        config = LoopConfig()

    events: list[AgentEvent] = []
    final_output = ""
    error = None

    async for event in agent_loop(llm, tool_registry, system_prompt, user_message, config):
        events.append(event)
        if event.type == "final":
            final_output = event.content
        elif event.type == "error":
            error = event.content

    total_cost = sum(e.cost_usd for e in events if e.type == "llm_call")
    total_tool_calls = sum(1 for e in events if e.type == "tool_call")
    iterations = sum(1 for e in events if e.type == "llm_call")

    return LoopResult(
        success=error is None and bool(final_output),
        output=final_output or error or "Agent produced no output",
        iterations=iterations,
        total_tool_calls=total_tool_calls,
        total_cost_usd=total_cost,
        events=events,
        error=error,
    )
