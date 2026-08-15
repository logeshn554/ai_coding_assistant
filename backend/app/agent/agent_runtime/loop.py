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
    run_id: str | None = None,
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

    from backend.app.config import config_manager
    from backend.app.shared_memory import sm_get, sm_set
    
    is_dual_llm = config_manager.get_dual_llm_mode()
    if is_dual_llm:
        system_prompt = (
            f"{system_prompt}\n\n"
            f"CRITICAL INSTRUCTION FOR DUAL-LLM EXECUTION MODE:\n"
            f"You are acting as the high-level Planner/Brain. You do NOT execute filesystem or terminal tools directly.\n"
            f"Instead, you orchestrate by writing tasks and context into the Shared Memory using the `shared_memory_set` tool:\n"
            f"1. Call `shared_memory_set` with key='generator_input' and value set to a JSON string or string containing only the necessary context, variables, files, or arguments needed by the generator LLM.\n"
            f"2. Call `shared_memory_set` with key='generator_task' containing a clear, concise instruction describing the tool invocation or code generation task you want the Generator LLM to execute.\n"
            f"Once you set 'generator_task', the Generator LLM will automatically run, execute the appropriate tool, and write the execution result to the Shared Memory under key 'generator_output'.\n"
            f"On your subsequent turns, you MUST call `shared_memory_get` with key='generator_output' to retrieve and analyze the generator's execution result."
        )

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

            # If dual_llm_mode is enabled, check if generator_task was set in shared memory
            if is_dual_llm:
                sm_key = run_id or "default"
                generator_task = await sm_get(sm_key, "generator_task")
                if generator_task:
                    generator_input = await sm_get(sm_key, "generator_input") or ""
                    
                    # Clear these keys immediately so we don't trigger again next time
                    await sm_set(sm_key, "generator_task", "")
                    await sm_set(sm_key, "generator_input", "")
                    
                    # Log / yield event
                    yield AgentEvent(
                        type="llm_call",
                        content=f"[Generator LLM] Delegated task: {generator_task}",
                    )
                    
                    # Call Generator LLM
                    generator_system = (
                        "You are the Generator/Executor LLM. Your job is to execute the delegated task using ONLY "
                        "the inputs provided from the shared memory. Do not assume or search for other context. "
                        "You must call the appropriate tool to complete this task."
                    )
                    generator_user = (
                        f"Delegated Task: {generator_task}\n\n"
                        f"Inputs from Shared Memory:\n{generator_input}\n\n"
                        f"Execute the task by calling the appropriate tool."
                    )
                    
                    try:
                        gen_messages = [
                            Message(role="system", content=generator_system),
                            Message(role="user", content=generator_user),
                        ]
                        secondary_model = config_manager.get_secondary_agent_model().strip()
                        gen_llm = llm
                        if secondary_model:
                            try:
                                from agent_runtime.llm.openai_provider import OpenAIProvider
                                secondary_profile_name = config_manager.get_secondary_agent_profile()
                                secondary_profile = None
                                if secondary_profile_name:
                                    secondary_profile = config_manager.get_profile(secondary_profile_name)
                                
                                profile_to_use = secondary_profile or config_manager.get_active_profile()
                                api_key = profile_to_use.get("api_key", "") if profile_to_use else ""
                                base_url = profile_to_use.get("base_url", "https://api.openai.com/v1") if profile_to_use else "https://api.openai.com/v1"
                                gen_llm = OpenAIProvider(api_key=api_key, model=secondary_model, base_url=base_url)
                                logger.info("Dual-LLM Mode: Generator using secondary_agent_model '%s' and profile '%s'", secondary_model, profile_to_use.get("name", "active") if profile_to_use else "active")
                            except Exception as sec_err:
                                logger.warning("Failed to initialize secondary LLM provider '%s': %s", secondary_model, sec_err)
                                gen_llm = llm

                        # Generator has access to all tools (e.g. filesystem, terminal)
                        gen_response = await gen_llm.generate(
                            messages=gen_messages,
                            tools=tool_schemas if tool_schemas else None,
                            temperature=0.0,
                            max_tokens=config.max_tokens,
                        )

                        
                        gen_result_str = ""
                        if gen_response.has_tool_calls:
                            yield AgentEvent(
                                type="llm_call",
                                content=f"[Generator LLM] Calling tools: {', '.join([tc.name for tc in gen_response.tool_calls])}",
                            )
                            for tool_call in gen_response.tool_calls:
                                yield AgentEvent(
                                    type="tool_call",
                                    tool_name=tool_call.name,
                                    tool_args=tool_call.arguments,
                                )
                                # Execute tool
                                res = await tool_registry.execute(tool_call.name, tool_call.arguments)
                                if res.success:
                                    res_text = res.output
                                else:
                                    res_text = f"Error: {res.error}" if res.error else "Tool execution failed"
                                
                                yield AgentEvent(
                                    type="tool_result",
                                    tool_name=tool_call.name,
                                    tool_result=res_text[:10_000],
                                )
                                if gen_result_str:
                                    gen_result_str += "\n\n"
                                gen_result_str += res_text
                        else:
                            gen_result_str = gen_response.content or "No output from Generator LLM."
                            
                        # Save result to shared memory
                        await sm_set(sm_key, "generator_output", gen_result_str)
                        
                        # Notify the Brain
                        messages.append(Message(
                            role="user",
                            content=(
                                f"System Notification: Generator LLM completed the task.\n"
                                f"Result has been stored in shared memory under key 'generator_output'.\n"
                                f"Please call `shared_memory_get` with key='generator_output' to inspect the results."
                            )
                        ))
                    except Exception as gen_err:
                        logger.error("Generator LLM invocation failed: %s", gen_err)
                        # Save error to shared memory
                        await sm_set(sm_key, "generator_output", f"Generator Error: {gen_err}")
                        messages.append(Message(
                            role="user",
                            content=f"System Notification: Generator LLM failed with error: {gen_err}"
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
    run_id: str | None = None,
) -> LoopResult:
    """Convenience wrapper that collects all events and returns a LoopResult.

    Use ``agent_loop()`` directly if you need to stream events in real-time.
    """
    if config is None:
        config = LoopConfig()

    events: list[AgentEvent] = []
    final_output = ""
    error = None

    async for event in agent_loop(llm, tool_registry, system_prompt, user_message, config, run_id):
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
