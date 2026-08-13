import json
import logging
import time
import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select, update
from backend.app.state import redis_client
from backend.app.infrastructure.database.models import AgentRun

logger = logging.getLogger("devpilot.infrastructure.queue")

QUEUE_NAME = "devpilot:queue:jobs"
PROCESSING_QUEUE_NAME = "devpilot:queue:processing"

class AgentQueue:
    @staticmethod
    async def enqueue(
        run_id: str,
        organization_id: str,
        user_id: str,
        project_id: str,
        workspace_id: str,
        priority: int = 0
    ) -> bool:
        job = {
            "run_id": run_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "project_id": project_id,
            "workspace_id": workspace_id,
            "attempt": 1,
            "priority": priority,
            "created_at": time.time(),
        }
        payload = json.dumps(job)
        res = await redis_client.rpush(QUEUE_NAME, payload)
        logger.info(f"Enqueued job for run {run_id} to queue {QUEUE_NAME} (queue size: {res})")
        return True

    @staticmethod
    async def claim_job() -> Optional[Dict[str, Any]]:
        """Atomically pop from source queue and push to processing queue."""
        payload = await redis_client.rpoplpush(QUEUE_NAME, PROCESSING_QUEUE_NAME)
        if not payload:
            return None
        try:
            return json.loads(payload)
        except Exception as e:
            logger.error(f"Failed to parse claimed job payload: {e}")
            await redis_client.lrem(PROCESSING_QUEUE_NAME, 0, payload)
            return None

    @staticmethod
    async def acknowledge_job(job: Dict[str, Any]) -> None:
        """Acknowledge job completion by removing it from the processing queue."""
        payload = json.dumps(job)
        await redis_client.lrem(PROCESSING_QUEUE_NAME, 0, payload)

    @staticmethod
    async def requeue_job(job: Dict[str, Any]) -> None:
        """Remove from processing and push back to main queue with incremented attempts."""
        old_payload = json.dumps(job)
        await redis_client.lrem(PROCESSING_QUEUE_NAME, 0, old_payload)
        
        job["attempt"] += 1
        new_payload = json.dumps(job)
        await redis_client.rpush(QUEUE_NAME, new_payload)
        logger.info(f"Requeued job for run {job['run_id']} for attempt {job['attempt']}")

    @staticmethod
    async def recover_stale_jobs(db_session, heartbeat_timeout_seconds: int = 60) -> None:
        """Find runs with expired heartbeats, mark them as INTERRUPTED, and transition their states."""
        now = datetime.datetime.utcnow()
        cutoff = now - datetime.timedelta(seconds=heartbeat_timeout_seconds)
        
        stmt = (
            select(AgentRun)
            .where(AgentRun.state == "RUNNING")
            .where(AgentRun.heartbeat_at < cutoff)
        )
        res = await db_session.execute(stmt)
        expired_runs = res.scalars().all()
        
        for run in expired_runs:
            logger.warning(f"Run {run.id} has expired heartbeat. Marking as INTERRUPTED for recovery.")
            run.state = "INTERRUPTED"
            run.status = "Worker heartbeat expired. Run marked interrupted."
            # Run state saved during commit
        await db_session.commit()
