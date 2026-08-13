import asyncio
import logging
import signal
import sys
import uuid
import time
import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import update, select
from backend.app.config import settings
from backend.app.state import redis_client, config_manager
from backend.app.infrastructure.queue import AgentQueue
from backend.app.infrastructure.database.connection import async_session_factory
from backend.app.infrastructure.database.models import AgentRun
from backend.app.infrastructure.database.repositories import AgentRunRepository
from backend.app.agent.agent_runtime.runtime import AgentRuntime, AgentState, AgentTask
from backend.app.agent.agent_runtime.llm_adapter import ModelResponse, ModelResponseNormalizer, ToolCall
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

    async def _resolve_workspace_root(self, run: AgentRun) -> str:
        """
        Resolve the real filesystem workspace root from the AgentRun record.
        Falls back gracefully so the worker never crashes with a DB URL as a path.
        """
        import os

        # 1. Prefer denormalized workspace_root column if present on AgentRun
        stored_root = getattr(run, "workspace_root", None)
        if stored_root and os.path.isdir(stored_root):
            return stored_root

        # 2. Resolve from associated Workspace.root_identifier
        if run.workspace and run.workspace.root_identifier:
            root = run.workspace.root_identifier
            if os.path.isdir(root):
                return root
            logger.warning(
                f"AgentRun {run.id}: workspace root_identifier '{root}' is not accessible. "
                "Falling back to current working directory."
            )

        # 3. Final fallback: current working directory (never the DB URL)
        cwd = os.getcwd()
        logger.warning(
            f"AgentRun {run.id}: Could not determine workspace root. Using cwd: {cwd}"
        )
        return cwd

    def _resolve_model_profile(self, run: AgentRun) -> Dict[str, Any]:
        """
        Resolve the model profile for this run from config_manager.
        Never exposes raw API keys in run records.
        """
        # Prefer profile stored at run-creation time
        stored_profile_name = getattr(run, "profile_name", None)
        if stored_profile_name:
            profile = config_manager.get_profile(stored_profile_name)
            if profile:
                logger.info(f"Worker: Using stored profile '{stored_profile_name}' for run {run.id}")
                return profile

        # Fallback to the currently active profile
        profile = config_manager.get_active_profile()
        if profile:
            logger.info(f"Worker: Using active profile '{profile.get('name', 'unknown')}' for run {run.id}")
            return profile

        # Return an empty dict; runtime will raise RuntimeError (P0-2)
        logger.warning(f"Worker: No model profile found for run {run.id}. Runtime will fail explicitly.")
        return {}

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

        # Resolve workspace root from run record — NEVER from settings.DATABASE_URL
        workspace_root = await self._resolve_workspace_root(run)

        # Resolve model profile from config_manager
        profile = self._resolve_model_profile(run)

        cancel_event = asyncio.Event()
        hb_task = asyncio.create_task(self.heartbeat_and_cancel_check(run_id, cancel_event))

        try:
            # Initialize runtime with correct workspace root
            runtime = AgentRuntime(workspace_root)
            session = await runtime.start_session(
                workspace_root,
                profile=profile,
                session_id=run_id,
            )

            async def on_event(event):
                await EventPublisher.publish(run_id, event.type, event.payload)

            task_obj = AgentTask(
                id=run_id,
                description=run.task_description,
                mode=run.mode,
            )

            # Build the real LLM provider function using ModelGateway
            from backend.app.infrastructure.model_gateway import ModelGateway
            from backend.app.adapters.tool_history import clean_tool_history

            async def llm_provider(messages: list, tools: list) -> ModelResponse:
                """
                Canonical LLM provider callback used by AgentRuntime.
                Uses the existing ModelGateway for retry, failover, and telemetry.
                Returns a normalized ModelResponse — never silently succeeds without calling LLM.
                """
                if not profile:
                    raise RuntimeError(
                        f"No model profile configured for run {run_id}. "
                        "Configure an LLM provider in settings before running the agent."
                    )

                cleaned_messages = clean_tool_history(messages)

                # Accumulate streaming chunks into a complete response
                text_parts: list = []
                tool_calls_raw: list = []
                finish_reason: Optional[str] = None
                total_input_tokens: int = 0
                total_output_tokens: int = 0

                async for chunk in ModelGateway.generate_stream(
                    profile,
                    cleaned_messages,
                    tools or [],
                    system_prompt=None,
                    task_type="coding",
                ):
                    chunk_type = chunk.get("type")
                    if chunk_type == "text":
                        text_parts.append(chunk.get("content", ""))
                    elif chunk_type == "tool_use":
                        tool_calls_raw.append(chunk)
                    elif chunk_type == "tool_calls":
                        raw_tcs = chunk.get("tool_calls", [])
                        tool_calls_raw.extend(raw_tcs)
                    elif chunk_type == "finish":
                        finish_reason = chunk.get("finish_reason")
                    elif chunk_type == "usage":
                        total_input_tokens += chunk.get("input_tokens", 0)
                        total_output_tokens += chunk.get("output_tokens", 0)
                        # Record usage against the run
                        try:
                            async with async_session_factory() as db:
                                await db.execute(
                                    update(AgentRun)
                                    .where(AgentRun.id == run_id)
                                    .values(
                                        error_message=None,  # clear any previous
                                    )
                                )
                                await db.commit()
                        except Exception:
                            pass

                full_text = "".join(text_parts) or None
                resp_dict = {
                    "content": full_text,
                    "tool_calls": tool_calls_raw,
                    "finish_reason": finish_reason,
                }
                return ModelResponseNormalizer.normalize_response(resp_dict)

            # Run the canonical execution path
            res = await runtime.run(
                session_id=run_id,
                task=task_obj,
                mode=run.mode,
                event_callback=on_event,
                llm_provider_func=llm_provider,
            )

            async with async_session_factory() as db:
                run_repo = AgentRunRepository(db)
                db_run = await run_repo.get_run(job["organization_id"], run_id)
                if db_run:
                    db_run.state = res.state.value if isinstance(res.state, AgentState) else str(res.state)
                    db_run.status = f"Completed execution. Status: {res.verification_status}"
                    db_run.completed_at = datetime.datetime.utcnow()
                    if not res.success:
                        db_run.error_message = "; ".join(res.errors[:5]) if res.errors else "Run did not succeed"
                    await db.commit()

        except Exception as run_err:
            logger.exception(f"process_run failed for {run_id}: {run_err}")
            try:
                async with async_session_factory() as db:
                    await db.execute(
                        update(AgentRun)
                        .where(AgentRun.id == run_id)
                        .values(
                            state="FAILED",
                            status="Worker process_run exception.",
                            error_code="WORKER_EXCEPTION",
                            error_message=str(run_err)[:2000],
                            completed_at=datetime.datetime.utcnow(),
                        )
                    )
                    await db.commit()
            except Exception:
                pass
            raise
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
                    if state in ("CANCELLED", "FAILED", "COMPLETED", "COMPLETED_VERIFIED"):
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
