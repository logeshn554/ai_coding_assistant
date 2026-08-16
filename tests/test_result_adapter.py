"""Unit tests for ResultAdapter: ensures deterministic single terminal event and error banner handling."""

import pytest
from typing import Any, Dict, List

from backend.app.agent.agent_runtime.runtime import AgentResult, AgentState, VerificationStatus
from backend.app.session.base_session import BaseSession
from backend.app.session.result_adapter import adapt_result


class DummySession(BaseSession):
    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.total_cost_usd = 0.042
        self.wasted_turns = 1

    async def send_ws_message(self, message: Dict[str, Any]) -> None:
        self.sent_messages.append(message)


@pytest.mark.asyncio
async def test_adapt_result_success():
    session = DummySession()
    res = AgentResult(
        session_id="run_123",
        task_id="task_123",
        success=True,
        state=AgentState.COMPLETED_VERIFIED,
        output="Successfully created unit tests.",
        changed_files={"created_files": ["test_sample.py"]},
        verification_status=VerificationStatus.PASSED,
        errors=[],
    )

    await adapt_result(res, session)

    # Must only emit 1 message: session_done (no error banner)
    assert len(session.sent_messages) == 1
    done_msg = session.sent_messages[0]
    assert done_msg["type"] == "session_done"
    assert done_msg["total_cost_usd"] == 0.042
    assert done_msg["wasted_turns"] == 1


@pytest.mark.asyncio
async def test_adapt_result_failure():
    session = DummySession()
    res = AgentResult(
        session_id="run_456",
        task_id="task_456",
        success=False,
        state=AgentState.FAILED,
        output="",
        changed_files={},
        verification_status=VerificationStatus.FAILED,
        errors=["SyntaxError in generated code", "Test suite failed"],
    )

    await adapt_result(res, session)

    # Must emit exactly 2 messages: 1 text_delta error banner + 1 session_done
    assert len(session.sent_messages) == 2
    
    err_banner = session.sent_messages[0]
    assert err_banner["type"] == "text_delta"
    assert "Agent Run Stopped (FAILED)" in err_banner["content"]
    assert "SyntaxError in generated code" in err_banner["content"]

    done_msg = session.sent_messages[1]
    assert done_msg["type"] == "session_done"
    assert done_msg["total_cost_usd"] == 0.042


@pytest.mark.asyncio
async def test_adapt_result_extra_payload():
    session = DummySession()
    res = AgentResult(
        session_id="run_789",
        task_id="task_789",
        success=True,
        state=AgentState.COMPLETED,
        output="Done",
    )

    extra = {
        "task_memory": {"goal": "build api"},
        "verification": {"passed": True},
    }

    await adapt_result(res, session, extra_payload=extra)

    assert len(session.sent_messages) == 1
    done_msg = session.sent_messages[0]
    assert done_msg["type"] == "session_done"
    assert done_msg["task_memory"] == {"goal": "build api"}
    assert done_msg["verification"] == {"passed": True}


@pytest.mark.asyncio
async def test_adapt_result_empty_response():
    session = DummySession()
    res = AgentResult(
        session_id="run_empty",
        task_id="task_empty",
        success=False,
        state=AgentState.EMPTY_RESPONSE,
        output="",
        errors=["Model provider returned empty response."],
    )

    await adapt_result(res, session)

    assert len(session.sent_messages) == 2
    err_banner = session.sent_messages[0]
    assert err_banner["type"] == "text_delta"
    assert "No Content Generated (EMPTY_RESPONSE)" in err_banner["content"]
    assert "Safety Filter" in err_banner["content"]

    done_msg = session.sent_messages[1]
    assert done_msg["type"] == "session_done"

