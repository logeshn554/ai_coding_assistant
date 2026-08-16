import pytest
import asyncio
import tempfile
import pathlib
from backend.app.agent.agent_runtime import (
    AgentRuntime,
    AgentState,
    AgentTask,
)
from backend.app.session.agent_session import AgentSession


@pytest.mark.asyncio
async def test_queue_worker_emits_error_on_uncaught_exception():
    """Verify that when an exception escapes handle_user_message, _queue_worker emits text_delta and session_done."""
    emitted_events = []

    async def mock_ws(msg):
        emitted_events.append(msg)

    with tempfile.TemporaryDirectory() as tmpdir:
        session = AgentSession(
            workspace_root=tmpdir,
            profile={},
            send_ws_message=mock_ws,
            session_id="test_worker_err_sess",
        )

        # Monkeypatch handle_user_message to simulate an unexpected crash
        async def crashing_handler(*args, **kwargs):
            raise ValueError("Simulated pipeline crash in handle_user_message")

        session.handle_user_message = crashing_handler

        # Enqueue message and wait for worker task to process it
        await session.enqueue_message("Hello", "Agent")
        if session._worker_task:
            await session._worker_task

        # Assert that an error card was emitted
        text_deltas = [e for e in emitted_events if e.get("type") == "text_delta"]
        assert len(text_deltas) > 0
        assert "Agent Worker Error" in text_deltas[0]["content"]
        assert "Simulated pipeline crash" in text_deltas[0]["content"]

        # Assert terminal session_done was emitted
        session_dones = [e for e in emitted_events if e.get("type") == "session_done"]
        assert len(session_dones) > 0


@pytest.mark.asyncio
async def test_runtime_handles_provider_exception_cleanly():
    """Verify that AgentRuntime converts provider exceptions into FAILED state with error events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = AgentRuntime(tmpdir)
        events_emitted = []

        async def failing_provider(messages, tools):
            raise ConnectionError("LLM API Gateway unreachable")

        result = await runtime.run(
            session_id="test_fail_sess",
            task="Analyze repo",
            event_callback=lambda ev: events_emitted.append(ev),
            llm_provider_func=failing_provider,
        )

        assert result.success is False
        assert result.state == AgentState.FAILED
        assert any("LLM API Gateway unreachable" in err for err in result.errors)


@pytest.mark.asyncio
async def test_checkpoint_ignores_stale_task_id():
    """Verify that load_checkpoint skips checkpoints from previous mismatched tasks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = AgentRuntime(tmpdir)
        session_state = await runtime.start_session(tmpdir, session_id="test_cp_sess")
        
        session_state.active_task_id = "old_task_123"
        session_state.state = AgentState.EXECUTING
        session_state.current_step = 5
        await runtime.save_checkpoint(session_state, "test_cp")

        # Create fresh session state instance and attempt loading with different task_id
        fresh_state = await runtime.start_session(tmpdir, session_id="test_cp_sess")
        loaded = await runtime.load_checkpoint(fresh_state, task_id="new_task_456")

        assert loaded is False
        assert fresh_state.current_step == 0


@pytest.mark.asyncio
async def test_cancel_all_cleans_queue_and_sets_status():
    """Verify cancel_all stops the worker and drains the queue cleanly."""
    emitted_events = []

    async def mock_ws(msg):
        emitted_events.append(msg)

    with tempfile.TemporaryDirectory() as tmpdir:
        session = AgentSession(
            workspace_root=tmpdir,
            profile={},
            send_ws_message=mock_ws,
            session_id="test_cancel_sess",
        )

        # Fill queue
        await session._message_queue.put(("msg1", "Agent", False))
        await session._message_queue.put(("msg2", "Agent", False))

        await session.cancel_all()

        assert session._message_queue.empty()
        assert session.is_running is False
        assert any(e.get("type") == "queue_status" and e.get("queue_depth") == 0 for e in emitted_events)


@pytest.mark.asyncio
async def test_checkpoint_saves_and_restores_error_code():
    """Verify that save_checkpoint stores error_code in state_json and load_checkpoint restores it."""
    from backend.app.infrastructure.database.connection import async_session_factory
    from backend.app.infrastructure.database.models import AgentCheckpoint
    from sqlalchemy import select
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = AgentRuntime(tmpdir)
        session_state = await runtime.start_session(tmpdir, session_id="test_cp_error_code_sess")

        session_state.state = AgentState.EXECUTING
        session_state.current_step = 2
        session_state.error_code = "EMPTY_RESPONSE"
        session_state.errors = ["Model provider returned empty response."]

        await runtime.save_checkpoint(session_state, "test_cp")

        # 1. Assert DB state_json directly contains error_code
        async with async_session_factory() as db:
            stmt = select(AgentCheckpoint).where(AgentCheckpoint.run_id == "test_cp_error_code_sess")
            res = await db.execute(stmt)
            cp = res.scalars().first()
            assert cp is not None
            data = json.loads(cp.state_json)
            assert data.get("error_code") == "EMPTY_RESPONSE"

        # 2. Assert load_checkpoint restores error_code onto fresh session instance
        fresh_state = await runtime.start_session(tmpdir, session_id="test_cp_error_code_sess")
        assert fresh_state.error_code is None

        loaded = await runtime.load_checkpoint(fresh_state)
        assert loaded is True
        assert fresh_state.error_code == "EMPTY_RESPONSE"
        assert fresh_state.current_step == 2


@pytest.mark.asyncio
async def test_checkpoint_handles_legacy_without_error_code():
    """Verify backward compatibility when loading legacy checkpoints lacking the error_code field."""
    from backend.app.infrastructure.database.connection import async_session_factory
    from backend.app.infrastructure.database.models import AgentCheckpoint
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = AgentRuntime(tmpdir)
        sess_id = "test_cp_legacy_sess"

        # Insert legacy checkpoint without error_code in JSON
        legacy_data = {
            "current_step": 3,
            "state": "EXECUTING",
            "active_task_id": "legacy_task",
            "verification_status": "NOT_RUN",
            "changed_files": {},
            "errors": ["Some older error"],
            "tool_calls_count": 1,
            "started_at": None,
        }
        async with async_session_factory() as db:
            cp = AgentCheckpoint(
                run_id=sess_id,
                checkpoint_name="legacy_cp",
                state_json=json.dumps(legacy_data),
            )
            db.add(cp)
            await db.commit()

        fresh_state = await runtime.start_session(tmpdir, session_id=sess_id)
        loaded = await runtime.load_checkpoint(fresh_state)
        assert loaded is True
        assert fresh_state.error_code is None
        assert fresh_state.current_step == 3
        assert fresh_state.state == AgentState.EXECUTING


@pytest.mark.asyncio
async def test_runtime_empty_response_failure_model():
    """Verify end-to-end that empty LLM responses result in FAILED state with error_code=EMPTY_RESPONSE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = AgentRuntime(tmpdir)

        async def empty_provider(messages, tools):
            return {"content": "", "tool_calls": []}

        result = await runtime.run(
            session_id="test_empty_resp_model_sess",
            task="Refactor codebase",
            llm_provider_func=empty_provider,
        )

        assert result.success is False
        assert result.state == AgentState.FAILED
        assert result.error_code == "EMPTY_RESPONSE"
        assert any("Model provider returned empty response" in err for err in result.errors)

