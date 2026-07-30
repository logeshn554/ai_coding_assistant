"""Question tool – agent asks user a clarifying question and awaits answer.

Exposes ``ask_question(session, tc_id, args)`` as the agent-facing
async function. Sends a ``question`` WebSocket message to the frontend
and blocks until the user answers or a timeout occurs.

The user's answer is returned as a string to the agent.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

QUESTION_TIMEOUT = 300  # seconds – 5 minutes for user to respond


async def ask_question(session: Any, tc_id: str, args: Dict[str, Any]) -> str:
    """Ask the user a clarifying question and return their answer.

    The agent's execution is paused until the user submits a response
    or the timeout expires.

    Args:
        session: Active AgentSession.
        tc_id: Tool call identifier.
        args:
            question (str, required): The question text to show the user.
            options (list[str], optional): If provided, present as multiple-
                choice options. The user may also type a free-form answer.
            context (str, optional): Additional context shown below the question.

    Returns:
        The user's answer string, or a timeout/error message.
    """
    question: str = (args.get("question") or "").strip()
    if not question:
        return "Error: 'question' argument is required."

    options = args.get("options") or []
    context: str = (args.get("context") or "").strip()

    # Send question message to frontend
    await session.send_ws_message({
        "type": "agent_question",
        "tool_call_id": tc_id,
        "question": question,
        "options": options,
        "context": context,
    })

    # Register a pending confirmation/answer slot
    if not hasattr(session, "pending_confirmations"):
        # Fallback: can't wait – return immediately
        return f"[Question asked: '{question}' – session does not support interactive questions]"

    answer_event = asyncio.Event()
    session.pending_confirmations[tc_id] = {
        "event": answer_event,
        "approved": False,
        "answer": None,
        "type": "question",
    }

    try:
        await asyncio.wait_for(answer_event.wait(), timeout=QUESTION_TIMEOUT)
    except asyncio.TimeoutError:
        session.pending_confirmations.pop(tc_id, None)
        return f"[Question timed out after {QUESTION_TIMEOUT}s. No answer received. Proceeding with best judgment.]"

    slot = session.pending_confirmations.pop(tc_id, {})
    answer = slot.get("answer") or slot.get("input") or ""

    if not answer:
        return "[User dismissed the question without answering. Proceeding with best judgment.]"

    return str(answer)
