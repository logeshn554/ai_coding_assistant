# backend/app/session/result_adapter.py
"""
ResultAdapter: centralizes translation of AgentResult into UI events.
Ensures exactly one `session_done` event and at most one error banner per request.
"""

from ..agent.agent_runtime.runtime import AgentResult, AgentState
from .base_session import BaseSession


async def adapt_result(
    run_res: AgentResult,
    session: BaseSession,
    extra_payload: dict | None = None,
) -> None:
    """Adapt an AgentResult into UI events.

    - Sends a single error banner if the run failed.
    - Sends a single ``session_done`` event with cost and turn info.
    - Does **not** emit ``EVENT_AGENT_ERROR`` directly; that is handled by the UI.
    """
    # If failure, construct an error message
    if not run_res.success:
        state_str = run_res.state.value if isinstance(run_res.state, AgentState) else str(run_res.state)
        error_code = getattr(run_res, "error_code", None)
        if error_code == "EMPTY_RESPONSE":
            fail_card = (
                "\n\n> ⚠️ **No Content Generated (EMPTY_RESPONSE)**\n\n"
                "The model provider returned an empty response or failed to generate text.\n\n"
                "**Common Causes & Fixes:**\n"
                "- **API Key / Quota**: Free-tier API rate limit or quota exceeded.\n"
                "- **Model Selection**: The selected provider or model may be temporarily unavailable.\n"
                "- **Safety Filter**: The prompt content was filtered by provider safety guardrails.\n\n"
                "💡 *Try resending your request, switching to another model profile in Settings, or starting a new session.*"
            )
        else:
            err_lines = [e for e in run_res.errors if e]
            err_detail = "\n".join(f"- {e}" for e in err_lines) if err_lines else "An unexpected error interrupted the execution."
            header = f"Agent Run Stopped ({state_str}: {error_code})" if error_code else f"Agent Run Stopped ({state_str})"
            fail_card = (
                f"\n\n> ⚠️ **{header}**\n\n"
                f"{err_detail}\n\n"
                f"💡 *You can retry the request or check your model configuration.*"
            )
        await session.send_ws_message({"type": "text_delta", "content": fail_card})

    # Always emit session_done (once) after handling result
    done_payload = {
        "type": "session_done",
        "total_cost_usd": getattr(session, "total_cost_usd", 0.0),
        "wasted_turns": getattr(session, "wasted_turns", 0),
    }
    if extra_payload:
        done_payload.update(extra_payload)

    await session.send_ws_message(done_payload)

