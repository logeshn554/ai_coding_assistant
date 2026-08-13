import asyncio
import datetime
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select, update

from backend.app.infrastructure.database.connection import async_session_factory
from backend.app.infrastructure.database.models import (
    Organization, User, Project, Workspace, Conversation, AgentRun, AgentCheckpoint
)
from backend.app.infrastructure.queue import AgentQueue
from backend.app.infrastructure.worker import AgentWorker, RunLock
from backend.app.agent.agent_runtime.runtime import AgentRuntime, AgentState, AgentResult, VerificationStatus

@pytest.mark.asyncio
async def test_worker_recovery():
    # Setup test entities
    async with async_session_factory() as db:
        from sqlalchemy import delete
        await db.execute(delete(AgentCheckpoint).where(AgentCheckpoint.run_id == "test-run-123"))
        await db.execute(delete(AgentRun).where(AgentRun.id == "test-run-123"))
        await db.commit()

        org = Organization(id="default-org", name="default-org")
        user = User(id="default-user", email="test@example.com", full_name="Test", hashed_password="mocked_password")
        proj = Project(id="test-proj", organization_id="default-org", name="Test Project")
        ws = Workspace(id="test-ws", organization_id="default-org", project_id="test-proj", name="Test WS", root_identifier="C:\\")
        conv = Conversation(id="test-conv", organization_id="default-org", user_id="default-user", workspace_id="test-ws", title="Test")
        
        await db.merge(org)
        await db.merge(user)
        await db.merge(proj)
        await db.merge(ws)
        await db.merge(conv)
        await db.commit()
        
        run = AgentRun(
            id="test-run-123",
            organization_id="default-org",
            user_id="default-user",
            project_id="test-proj",
            workspace_id="test-ws",
            conversation_id="test-conv",
            task_description="Test recovery task",
            mode="Agent",
            state="QUEUED"
        )
        await db.merge(run)
        await db.commit()

    # 1. Enqueue job
    await AgentQueue.enqueue(
        run_id="test-run-123",
        organization_id="default-org",
        user_id="default-user",
        project_id="test-proj",
        workspace_id="test-ws"
    )

    # 2. Simulate worker 1 starting execution and saving a checkpoint
    runtime = AgentRuntime("worker-1")
    session = await runtime.start_session("C:\\", session_id="test-run-123")
    session.current_step = 2
    session.state = AgentState.EXECUTING
    await runtime.save_checkpoint(session, "test_checkpoint")

    # Verify checkpoint exists
    async with async_session_factory() as db:
        res = await db.execute(select(AgentCheckpoint).where(AgentCheckpoint.run_id == "test-run-123"))
        checkpoints = res.scalars().all()
        assert len(checkpoints) == 1
        assert checkpoints[0].checkpoint_name == "test_checkpoint"

    # 3. Simulate Worker 1 crashing (heartbeat stale)
    stale_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=120)
    async with async_session_factory() as db:
        await db.execute(
            update(AgentRun)
            .where(AgentRun.id == "test-run-123")
            .values(state="RUNNING", heartbeat_at=stale_time)
        )
        await db.commit()

    # 4. Trigger recovery
    async with async_session_factory() as db:
        await AgentQueue.recover_stale_jobs(db, heartbeat_timeout_seconds=60)
        
        res = await db.execute(select(AgentRun).where(AgentRun.id == "test-run-123"))
        run = res.scalar()
        assert run.state == "INTERRUPTED"

    # 5. Start Worker 2 to process and recover the run
    worker2 = AgentWorker("worker-2")
    job = {
        "run_id": "test-run-123",
        "organization_id": "default-org",
        "user_id": "default-user",
        "project_id": "test-proj",
        "workspace_id": "test-ws",
        "attempt": 1
    }
    
    mock_result = AgentResult(
        session_id="test-run-123",
        task_id="test-run-123",
        success=True,
        state=AgentState.COMPLETED_VERIFIED,
        output="Successfully completed after recovery!",
        verification_status=VerificationStatus.PASSED
    )
    
    with patch.object(AgentRuntime, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        
        lock_token = await RunLock.acquire("test-run-123")
        assert lock_token is not None
        
        try:
            await worker2.process_run(job, lock_token)
        finally:
            await RunLock.release("test-run-123", lock_token)

    # 6. Verify run state in database is updated to COMPLETED_VERIFIED
    async with async_session_factory() as db:
        res = await db.execute(select(AgentRun).where(AgentRun.id == "test-run-123"))
        run = res.scalar()
        assert run.state == "COMPLETED_VERIFIED"
        assert "Completed execution" in run.status
