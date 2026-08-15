import asyncio
import logging
import signal
import sys
import uuid
import time
import datetime
import json
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
from backend.app.agent.agent_runtime.events import AgentEvent
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
            except Exception:
                logger.exception("Worker loop error")
                await asyncio.sleep(1.0)

    async def _resolve_workspace_root(self, run: AgentRun) -> str:
        """
        Resolve the real filesystem workspace root from the AgentRun record.

        Fail-closed: raises RuntimeError if no valid workspace can be found.
        Never falls back to cwd — that would silently corrupt an unrelated directory.
        Never uses DATABASE_URL or any non-path value as a workspace root.
        """
        import os

        # 1. Prefer denormalized workspace_root column stored at run-creation time
        stored_root = getattr(run, "workspace_root", None)
        if stored_root:
            # Sanity guard: reject anything that looks like a DB connection string
            if stored_root.startswith(("sqlite", "postgresql", "mysql", "http", "redis")):
                raise RuntimeError(
                    f"AgentRun {run.id}: workspace_root '{stored_root}' looks like a DB URL, "
                    "not a filesystem path. Cannot execute safely."
                )
            if os.path.isdir(stored_root):
                return stored_root
            raise RuntimeError(
                f"AgentRun {run.id}: stored workspace_root '{stored_root}' is not an accessible "
                "directory. Refusing to execute — fix the workspace configuration."
            )

        # 2. Resolve from associated Workspace.root_identifier
        if run.workspace and run.workspace.root_identifier:
            root = run.workspace.root_identifier
            if os.path.isdir(root):
                logger.info(f"AgentRun {run.id}: resolved workspace from Workspace record: {root}")
                return root
            raise RuntimeError(
                f"AgentRun {run.id}: Workspace.root_identifier '{root}' is not an accessible "
                "directory. Refusing to execute — fix the workspace configuration."
            )

        # 3. No valid workspace found — fail explicitly (never silently fallback to cwd)
        raise RuntimeError(
            f"AgentRun {run.id}: No workspace root configured. "
            "Set workspace_root on the run or configure a Workspace with a valid root_identifier."
        )

    def _resolve_model_profile(self, run: AgentRun) -> Dict[str, Any]:
        """
        Resolve the model profile for this run from config_manager.

        Profile immutability: if the run was created with profile_name X, always use X.
        If X no longer exists, raise RuntimeError — never silently switch to the active profile.
        Never exposes raw API keys in run records.
        """
        stored_profile_name = getattr(run, "profile_name", None)
        if stored_profile_name:
            profile = config_manager.get_profile(stored_profile_name)
            if profile:
                logger.info(
                    f"Worker: Using stored profile '{stored_profile_name}' for run {run.id}"
                )
                return profile
            # Profile was recorded at run-creation time but no longer exists — fail explicitly
            raise RuntimeError(
                f"AgentRun {run.id}: Model profile '{stored_profile_name}' no longer exists. "
                "Cannot switch providers silently. Reconfigure or re-create the run."
            )

        # No profile was stored at run-creation time — fall back to primary agent profile if set
        primary_profile_name = config_manager.get_primary_agent_profile()
        if isinstance(primary_profile_name, str) and primary_profile_name.strip():
            profile = config_manager.get_profile(primary_profile_name)
            if profile:
                logger.info(
                    f"Worker: No profile stored for run {run.id}. "
                    f"Using primary agent profile '{primary_profile_name}'"
                )
                return profile

        # Fallback to active profile
        profile = config_manager.get_active_profile()
        if profile:
            logger.info(
                f"Worker: No profile stored for run {run.id}. "
                f"Using active profile '{profile.get('name', 'unknown')}'"
            )
            return profile

        # No profile anywhere — runtime will raise RuntimeError
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

            from backend.app.agent.agent_runtime.events import AgentEvent as RuntimeAgentEvent

            async def on_event(event):
                if hasattr(event, "type") and hasattr(event, "payload"):
                    await EventPublisher.publish(run_id, event.type, event.payload)
                elif isinstance(event, dict):
                    evt_type = event.get("type", "unknown")
                    payload = {k: v for k, v in event.items() if k not in ("type", "session_id", "run_id")}
                    await EventPublisher.publish(run_id, evt_type, payload)

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
                model_name = profile.get("model_name") or profile.get("model")
                provider = profile.get("provider") or profile.get("api_format")
                api_key = profile.get("api_key")
                base_url = profile.get("base_url")

                if not model_name or str(model_name).strip() == "":
                    raise RuntimeError("Active model configuration is missing model name.")
                if not provider or str(provider).strip() == "":
                    model_l = (model_name or "").lower()
                    url_l = (base_url or "").lower()
                    if "anthropic" in url_l or "claude" in model_l:
                        provider = "anthropic"
                    elif "generativelanguage" in url_l or "gemini" in model_l:
                        provider = "google"
                    else:
                        provider = "openai"
                if not api_key or str(api_key).strip() == "":
                    is_local_or_mock = (
                        (provider and provider.lower() in ("ollama", "mock", "local", "other"))
                        or "localhost" in (base_url or "").lower()
                        or "127.0.0.1" in (base_url or "").lower()
                    )
                    if not is_local_or_mock:
                        raise RuntimeError("Active model configuration is missing API key.")
                if (provider.lower() == "mock" or model_name.lower() == "mock") and os.environ.get("AGENT_RUNTIME_MODE", "").lower() != "mock":
                    raise RuntimeError("Mock provider/model configuration is not allowed in production agent path.")

                logger.info(
                    "LLM Request: provider=%s, model=%s, message_count=%d, tool_count=%d",
                    provider, model_name, len(messages), len(tools or [])
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
                        content = chunk.get("content", "")
                        text_parts.append(content)
                        await on_event(RuntimeAgentEvent(run_id, "text_delta", {"content": content}))
                    elif chunk_type == "thinking":
                        content = chunk.get("content", "")
                        await on_event(RuntimeAgentEvent(run_id, "thinking", {"content": content}))
                    elif chunk_type in ("tool_call", "tool_use"):
                        tc_id = chunk.get("id", "")
                        tc_name = chunk.get("name", "")
                        tc_args = chunk.get("input", {})
                        tc_sig = chunk.get("thought_signature")
                        logger.info("LLM Tool Call Chunk: id=%s, name=%s, args=%s, has_sig=%s", tc_id, tc_name, tc_args, bool(tc_sig))
                        tool_calls_raw.append({
                            "id": tc_id,
                            "name": tc_name,
                            "input": tc_args,
                            "arguments": tc_args,
                            "thought_signature": tc_sig,
                        })
                    elif chunk_type == "tool_calls":
                        raw_tcs = chunk.get("tool_calls", [])
                        for tc in raw_tcs:
                            logger.info("LLM Tool Call: id=%s, name=%s, args=%s", tc.get("id"), tc.get("name"), tc.get("arguments"))
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

                full_text = "".join(text_parts) or ""
                if not full_text.strip() and not tool_calls_raw:
                    logger.warning("LLM returned empty response body without tool calls. Providing graceful default summary.")
                    full_text = "I have processed the workspace state and request."

                logger.info(
                    "LLM Response received: content_len=%d, tool_calls_count=%d, finish_reason=%s",
                    len(full_text), len(tool_calls_raw), finish_reason
                )

                resp_dict = {
                    "content": full_text,
                    "tool_calls": tool_calls_raw,
                    "finish_reason": finish_reason,
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                    }
                }
                return ModelResponseNormalizer.normalize_response(resp_dict)

            # Load conversation history from DB to pass to runtime
            existing_messages = []
            async with async_session_factory() as db:
                from backend.app.infrastructure.database.models import Conversation
                stmt = select(Conversation.messages_json).where(Conversation.id == run.conversation_id)
                db_res = await db.execute(stmt)
                messages_json = db_res.scalar()
                if messages_json:
                    try:
                        existing_messages = json.loads(messages_json)
                    except Exception:
                        pass

            if not existing_messages:
                existing_messages = [{"role": "user", "content": run.task_description}]
            else:
                existing_messages.append({"role": "user", "content": run.task_description})

            # Run the canonical execution path
            res = await runtime.run(
                session_id=run_id,
                task=task_obj,
                mode=run.mode,
                event_callback=on_event,
                llm_provider_func=llm_provider,
                conversation_messages=existing_messages,
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
                await EventPublisher.publish(
                    run_id,
                    "agent.error",
                    {"error": str(run_err), "errors": [str(run_err)]}
                )
            except Exception as pub_err:
                logger.error(f"Failed to publish error event for run {run_id}: {pub_err}")
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
            if existing_messages:
                try:
                    async with async_session_factory() as db:
                        from backend.app.infrastructure.database.models import Conversation, Message
                        stmt = select(Conversation).where(Conversation.id == run.conversation_id)
                        db_res = await db.execute(stmt)
                        conv = db_res.scalar()
                        if conv:
                            conv.messages_json = json.dumps(existing_messages)
                            conv.updated_at = datetime.datetime.utcnow()

                            # Sync relational messages table
                            msg_stmt = select(Message).where(Message.conversation_id == run.conversation_id).order_by(Message.sequence.asc())
                            msg_res = await db.execute(msg_stmt)
                            existing_db_msgs = msg_res.scalars().all()
                            n_existing = len(existing_db_msgs)

                            for i, m in enumerate(existing_messages):
                                if i < n_existing:
                                    continue
                                role = m.get("role", "assistant")
                                content = m.get("content", "")
                                tool_calls = m.get("tool_calls")
                                thinking_blocks = m.get("thinking_blocks")
                                thinkingSteps = m.get("thinkingSteps")
                                if role == "assistant":
                                    db_content = json.dumps({
                                        "content": content if content is not None else "",
                                        "tool_calls": tool_calls,
                                        "thinking_blocks": thinking_blocks,
                                        "thinkingSteps": thinkingSteps,
                                    })
                                elif role == "tool":
                                    db_content = json.dumps({
                                        "content": content if content is not None else "",
                                        "tool_call_id": m.get("tool_call_id") or "",
                                        "name": m.get("name") or ""
                                    })
                                elif isinstance(content, (dict, list)):
                                    db_content = json.dumps(content)
                                else:
                                    db_content = content if content is not None else ""

                                db_msg = Message(
                                    conversation_id=run.conversation_id,
                                    role=role,
                                    content=db_content,
                                    sequence=i + 1,
                                    created_at=datetime.datetime.utcnow(),
                                )
                                db.add(db_msg)

                            await db.commit()
                except Exception as db_save_err:
                    logger.error(f"Failed to auto-save history to DB in worker: {db_save_err}")
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
