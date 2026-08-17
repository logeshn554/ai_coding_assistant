"""Spawn a stateless, read-only sub-agent to answer a self-contained prompt.

Modeled on the opencode agent-tool pattern: single-shot, no follow-up questions,
restricted to read-only tools.  The caller must embed all necessary context in
*prompt* — the sub-agent cannot ask follow-up questions.
"""

from __future__ import annotations

import logging
from typing import Any

from ..adapters.base import AVAILABLE_TOOLS
from ..adapters.router import ModelRouter

logger = logging.getLogger("loopix.tools.spawn_subagent")

# Tools the sub-agent is allowed to call.  Excludes run_terminal_command,
# write_file, edit_file, and open_with_live_server (all mutative / side-effecting).
_SUBAGENT_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {"list_directory", "read_file", "search_codebase"}
)

_SUBAGENT_SYSTEM_PROMPT = (
    "You are a read-only sub-agent spawned to answer a single, self-contained question. "
    "You have access only to read-only tools: list_directory, read_file, search_codebase. "
    "You MUST NOT attempt to write, edit, or delete files or run terminal commands. "
    "Answer the prompt fully and concisely, then stop. "
    "Do not ask follow-up questions — your response is final."
)


async def spawn_subagent(session: Any, prompt: str) -> str:
    """Spawn a disposable, stateless, read-only sub-agent to answer *prompt*.

    Stateless, one-shot.  The sub-agent cannot ask follow-up questions — prompt
    must be fully self-contained.  This mirrors the opencode AgentToolName pattern:
    a lightweight single-turn agent-as-a-tool that isolates its execution context
    from the parent session so no internal message log leaks back.

    The sub-agent is restricted to READ-ONLY tools only:
    ``list_directory``, ``read_file``, and ``search_codebase``.
    ``run_terminal_command``, ``write_file``, and ``edit_file`` are explicitly
    excluded from the sub-agent's toolset.

    Any cost accrued during sub-agent execution is rolled up into the parent
    session's ``total_cost_usd`` before returning.

    Args:
        session: The parent ``AgentSession``.  Provides workspace root, profile,
            and ``total_cost_usd`` for cost roll-up.
        prompt: A fully self-contained prompt.  The sub-agent cannot ask
            follow-up questions, so embed all necessary context here.

    Returns:
        The sub-agent's final text response.  Internal tool calls and
        intermediate messages are NOT included in the return value.

    Raises:
        RuntimeError: If the sub-agent produces no text response within the
            turn limit.
    """
    # Build the restricted toolset: keep only read-only tool schemas.
    read_only_tools = [
        t for t in AVAILABLE_TOOLS if t["name"] in _SUBAGENT_ALLOWED_TOOLS
    ]

    # Isolated message history — never touches parent session.conversation_history.
    messages: list[dict] = [{"role": "user", "content": prompt}]

    router = ModelRouter()
    adapter = router.get_adapter(session.profile, is_agent=False)

    sub_cost_usd: float = 0.0
    final_text: str = ""
    max_turns = 5  # sub-agent is capped at far fewer turns than the parent

    for _turn in range(max_turns):
        response_text = ""
        tool_calls_found: list[dict] = []

        try:
            async for chunk in adapter.stream_chat(messages, read_only_tools, _SUBAGENT_SYSTEM_PROMPT):
                ctype = chunk.get("type")
                if ctype == "text":
                    response_text += chunk["content"]
                elif ctype == "tool_call":
                    tool_calls_found.append(chunk)
                elif ctype == "usage":
                    # Some adapters emit token usage; collect cost when present.
                    sub_cost_usd += float(chunk.get("cost_usd", 0.0))
        except Exception as exc:
            logger.warning("spawn_subagent: LLM call failed on turn %d: %s. Returning fallback.", _turn + 1, exc)
            final_text = f"Sub-agent could not complete (LLM unavailable: {exc})"
            break

        # Append assistant turn to isolated history.
        asst_msg: dict = {"role": "assistant", "content": response_text}
        if tool_calls_found:
            asst_msg["tool_calls"] = [
                {"id": tc["id"], "name": tc["name"], "input": tc["input"]}
                for tc in tool_calls_found
            ]
        messages.append(asst_msg)

        if not tool_calls_found:
            # No tool calls → model is done.
            final_text = response_text
            break

        # Execute the read-only tool calls.
        tool_results: list[dict] = []
        for tc in tool_calls_found:
            tc_name = tc["name"]
            tc_args = tc.get("input", {})

            # Enforce the read-only boundary — raise on any forbidden tool.
            if tc_name not in _SUBAGENT_ALLOWED_TOOLS:
                error_msg = (
                    f"Tool '{tc_name}' is not available to sub-agents. "
                    "Sub-agents are restricted to read-only tools: "
                    + ", ".join(sorted(_SUBAGENT_ALLOWED_TOOLS))
                    + "."
                )
                logger.warning("spawn_subagent: blocked forbidden tool '%s'", tc_name)
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc_name,
                        "content": f"ERROR: {error_msg}",
                    }
                )
                continue

            # Dispatch the allowed read-only tool.
            try:
                from ..tools import file_tools, search_tool

                if tc_name == "list_directory":
                    result = await file_tools.list_directory(session, tc_args)
                elif tc_name == "read_file":
                    result = await file_tools.read_file(session, tc_args)
                elif tc_name == "search_codebase":
                    result = await search_tool.search_codebase(session, tc_args)
                else:
                    result = f"ERROR: Tool '{tc_name}' not handled."
            except Exception as exc:
                result = f"Tool '{tc_name}' error: {exc}"
                logger.warning("spawn_subagent: tool '%s' raised: %s", tc_name, exc)

            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc_name,
                    "content": result,
                }
            )

        messages.extend(tool_results)

    else:
        # Exhausted max_turns without a clean stop — return whatever we have.
        logger.warning("spawn_subagent: reached max_turns (%d) without clean stop", max_turns)
        final_text = response_text

    # Roll sub-agent cost into parent session (best-effort; attribute may not exist).
    if sub_cost_usd > 0.0:
        try:
            session.total_cost_usd = getattr(session, "total_cost_usd", 0.0) + sub_cost_usd
        except Exception:
            pass  # cost roll-up is non-critical

    logger.info("spawn_subagent: completed. cost=%.6f usd", sub_cost_usd)
    return final_text
