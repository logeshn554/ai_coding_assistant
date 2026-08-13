import asyncio
import logging
import signal
import sys
import uuid
import time
import datetime
from typing import Optional, Dict, Any
from sqlalchemy import update, select
from backend.app.config import settings
from backend.app.state import redis_client
from backend.app.infrastructure.queue import AgentQueue
from backend.app.infrastructure.database.connection import async_session_factory
from backend.app.infrastructure.database.models import AgentRun
from backend.app.infrastructure.database.repositories import AgentRunRepository
from backend.app.agent.agent_runtime.runtime import AgentRuntime, AgentState, AgentTask
from backend.app.infrastructure.events import EventPublisher

logger = logging.getLogger("devpilot.infrastructure.worker")

class RunLock:
    @staticmethod
    async def acquire(run_id: str, lease_seconds: int = 60) -> Optional[str]:
        lock_key = f"lock:agent-run:{run_id}"
        token = str(uuid.uuid4())
        if not redis_client.use_fallback:
            try:
                client = await redis_client._ensure_client()
                res = await client.set(lock_key, token, ex=lease_seconds, nx=True)
                if res:
                    return token
                return None
            except Exception:
                pass
        now = time.monotonic()
        expiry = redis_client._fallback_expiry.get(lock_key, 0)
        if expiry > now:
            return None
        redis_client.fallback_db[lock_key] = token
        redis_client._fallback_expiry[lock_key] = now + lease_seconds
        return token

    @staticmethod
    async def release(run_id: str, token: str) -> None:
        lock_key = f"lock:agent-run:{run_id}"
        if not redis_client.use_fallback:
            try:
                client = await redis_client._ensure_client()
                script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                await client.eval(script, 1, lock_key, token)
                return
            except Exception:
                pass
        if redis_client.fallback_db.get(lock_key) == token:
            redis_client.fallback_db.pop(lock_key, None)
            redis_client._fallback_expiry.pop(lock_key, None)


class AgentWorker:
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.should_stop = asyncio.Event()

    async def start(self):
        logger.info(f"Starting AgentWorker {self.worker_id}")
        
        # Set up shutdown signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.shutdown)
            except NotImplementedError:
                pass
                
        while not self.should_stop.is_set():
            try:
                # 1. Recover stale runs
                async with async_session_factory() as db:
                    await AgentQueue.recover_stale_jobs(db)
                
                # 2. Claim next job
                job = await AgentQueue.claim_job()
                if not job:
                    await asyncio.sleep(1.0)
                    continue
                    
                run_id = job["run_id"]
                logger.info(f"Worker {self.worker_id} claimed job for run {run_id}")
                
                # 3. Acquire distributed run lock lease
                lock_token = await RunLock.acquire(run_id)
                if not lock_token:
                    logger.warning(f"Could not acquire run lock for run {run_id}. Requeueing job.")
                    await AgentQueue.requeue_job(job)
                    await asyncio.sleep(1.0)
                    continue
                    
                try:
                    await self.process_run(job, lock_token)
                    await AgentQueue.acknowledge_job(job)
                except Exception as run_err:
                    logger.error(f"Error processing run {run_id}: {run_err}")
                    if job["attempt"] < 3:
                        await AgentQueue.requeue_job(job)
                    else:
                        logger.error(f"Job for run {run_id} failed after maximum attempts. Moving to dead letter.")
                        async with async_session_factory() as db:
                            await db.execute(
                                update(AgentRun)
                                .where(AgentRun.id == run_id)
                                .values(
                                    state="FAILED",
                                    status="Failed after maximum retries.",
                                    error_code="MAX_RETRIES_EXCEEDED",
                                    error_message=str(run_err)
                                )
                            )
                            await db.commit()
                        await AgentQueue.acknowledge_job(job)
                finally:
                    await RunLock.release(run_id, lock_token)
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1.0)

    async def process_run(self, job: dict, lock_token: str):
        run_id = job["run_id"]
        
        async with async_session_factory() as db:
            run_repo = AgentRunRepository(db)
            run = await run_repo.get_run(job["organization_id"], run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found in database.")
                
            run.state = "INITIALIZING"
            run.worker_id = self.worker_id
            run.heartbeat_at = datetime.datetime.utcnow()
            await db.commit()
            
        cancel_event = asyncio.Event()
        hb_task = asyncio.create_task(self.heartbeat_and_cancel_check(run_id, cancel_event))
        
        try:
            runtime = AgentRuntime(self.worker_id)
            async def on_event(event):
                await EventPublisher.publish(run_id, event.type, event.payload)
                
            await runtime.start_session(settings.DATABASE_URL, session_id=run_id)
            
            task_obj = AgentTask(
                id=run_id,
                description=run.task_description,
                mode=run.mode,
            )
            
            res = await runtime.run(
                session_id=run_id,
                task=task_obj,
                mode=run.mode,
                event_callback=on_event,
            )
            
            async with async_session_factory() as db:
                run_repo = AgentRunRepository(db)
                db_run = await run_repo.get_run(job["organization_id"], run_id)
                if db_run:
                    db_run.state = res.state.value if isinstance(res.state, AgentState) else str(res.state)
                    db_run.status = f"Completed execution. Status: {res.verification_status}"
                    db_run.completed_at = datetime.datetime.utcnow()
                    await db.commit()
        finally:
            cancel_event.set()
            await hb_task

    async def heartbeat_and_cancel_check(self, run_id: str, cancel_event: asyncio.Event):
        while not cancel_event.is_set():
            try:
                await asyncio.sleep(5.0)
                async with async_session_factory() as db:
                    await db.execute(
                        update(AgentRun)
                        .where(AgentRun.id == run_id)
                        .values(heartbeat_at=datetime.datetime.utcnow())
                    )
                    await db.commit()
                    
                    res = await db.execute(
                        select(AgentRun.state)
                        .where(AgentRun.id == run_id)
                    )
                    state = res.scalar()
                    if state in ("CANCELLED", "FAILED", "COMPLETED"):
                        cancel_event.set()
            except Exception as e:
                logger.error(f"Heartbeat check error for run {run_id}: {e}")

    def shutdown(self, *args):
        logger.info("Graceful shutdown received. Stopping worker consumption loop.")
        self.should_stop.set()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    worker = AgentWorker()
    asyncio.run(worker.start())
