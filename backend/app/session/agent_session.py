"""AgentSession: conversation loop, tool guardrails, and run-agent flow."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
import httpx
from typing import Optional
from ..adapters.base import AVAILABLE_TOOLS
from ..async_files import async_list_workspace_dir
from ..files import safe_path
from ..orchestrator import AgentOrchestrator
from ..processes import global_process_manager, get_process_using_port, kill_process_by_pid
from ..prompts.master import (
    AGENT_ORCHESTRATION_SECTION,
    render_system_prompt,
)
from ..prompts.modes import (
    AGENT_MODE_INSTRUCTIONS,
    ASK_MODE_INSTRUCTIONS,
    PLAN_MODE_INSTRUCTIONS,
)
from ..tools.dispatcher import dispatch_tool
from ..tools.terminal_tool import run_shell_command

# ── 14-Phase Agent Intelligence Layer ────────────────────────────────────────
from ..agent.intent_router import IntentRouter, IntentType
from ..agent.context_collector import ContextCollector
from ..agent.task_memory import TaskMemory, TaskStatus
from ..agent.planning_engine import PlanningEngine
from ..agent.execution_logger import ExecutionLogger
from ..agent.tool_policy import ToolPolicy
from ..agent.recovery_manager import RecoveryManager
from ..agent.knowledge_store import KnowledgeStore
from ..agent.confidence_scorer import ConfidenceScorer
from ..agent.validator import Validator
from ..agent.critic import Critic
from ..agent.workflow_engine import WorkflowEngine

logger = logging.getLogger("devpilot.agent")


def detect_contradiction(text: str) -> Optional[str]:
    """Detect contradictory instructions in user prompts.
    
    Allows multi-language, multi-framework, and fullstack setup instructions (e.g., Python + TypeScript,
    React + FastAPI) without raising false positive warnings.
    """
    text_lower = text.lower()
    
    # Check for mutually exclusive file operations (e.g. delete and edit/create/write) on the exact same file in one prompt
    words = re.findall(r'\b[\w\.\-]+\b', text_lower)
    files = [w for w in words if '.' in w and not w.endswith('.')]
    for f in files:
        has_delete = any(x in text_lower for x in (f"delete {f}", f"remove {f}", f"rm {f}", f"destroy {f}"))
        has_modify = any(x in text_lower for x in (f"edit {f}", f"modify {f}", f"update {f}", f"write {f}", f"create {f}", f"add to {f}"))
        if has_delete and has_modify:
            return f"The prompt contains mutually contradictory actions to delete and modify the file '{f}' in the same turn."

    return None


class AgentSession:
    """Manages a single DevPilot agent conversation and tool execution.

    Coordinates LLM streaming, tool dispatch with user confirmations,
    message queuing, multi-agent orchestration, and the Run Agent flow.
    """

    # Maximum number of messages that can be queued while an agent is running.
    # Beyond this limit new messages are rejected with a queue_full event.
    MAX_QUEUE_DEPTH = 10

    def __init__(
        self,
        workspace_root: str,
        profile: dict,
        send_ws_message,
        permission_manager=None,
        session_id=None,
    ):
        self.workspace_root = workspace_root
        self.profile = profile
        self.send_ws_message = send_ws_message
        self.permission_manager = permission_manager
        from ..agent.agent_runtime import AgentRuntime
        self.agent_runtime = AgentRuntime(self.workspace_root)
        self.orchestrator = AgentOrchestrator(session=self)
        self.conversation_history = []
        self.pending_confirmations = {}  # tool_call_id -> {"event": asyncio.Event(), "approved": bool}
        max_turns_config = profile.get("max_turns") or profile.get("max_orchestrator_steps") or 25
        self.max_turns = int(max_turns_config)
        self.audit_log = []
        self.is_running = False
        self.active_task = None
        self.session_id = session_id or "default-session"
        self.last_mode = "Ask"
        self.parallel_subtasks = []
        self.collaboration_log = []
        # Optional editor context used to select relevant skills.md sections.
        self.open_languages: list[str] = []
        self.open_files: list[str] = []
        # A8: Count turns wasted on timeouts, cancellations, and edit mismatches.
        self.wasted_turns: int = 0
        # B6: Store background monitor tasks so they can be cancelled in cancel_all().
        self._monitor_tasks: list[asyncio.Task] = []
        # B9: Cached WorkspaceIndex instance — reused across turns within a session
        # instead of being re-created on every LLM call (which discards the mtime cache).
        self._workspace_index = None
        self._failed_request = None
        self._last_request_snapshot = None
        self.total_cost_usd: float = 0.0
        self._cost_advisory_sent: bool = False
        self._db_saved_up_to: int = 0
        self._msg_size_cache: dict[int, int] = {}
        # System prompt cache: avoid rebuilding the full prompt on every LLM turn.
        # Keyed by (mode, workspace_mtime) — invalidated when files change.
        self._cached_system_prompt: dict[str, tuple[float, str]] = {}


        # ── 14-Phase Agent Intelligence Layer ────────────────────────────
        self.task_memory: TaskMemory = TaskMemory()
        self._intent_router: IntentRouter = IntentRouter()
        self._context_collector: ContextCollector = ContextCollector(workspace_root)
        self._planning_engine: PlanningEngine = PlanningEngine()
        self._tool_policy: ToolPolicy = ToolPolicy()
        self._recovery_manager: RecoveryManager = RecoveryManager()
        self._knowledge_store: KnowledgeStore = KnowledgeStore(workspace_root)
        self._confidence_scorer: ConfidenceScorer = ConfidenceScorer()
        self._validator: Validator = Validator(workspace_root)
        self._critic: Critic = Critic()
        self._workflow_engine: WorkflowEngine = WorkflowEngine()
        self._exec_logger: Optional[ExecutionLogger] = None
        self._current_intent: Optional[IntentType] = None
        self._agent_tool_call_count: int = 0  # total tool calls in current agent run

        # Request queue: new messages are enqueued while the agent is busy.
        # Each item is a tuple of (text, mode, auto_apply).
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_QUEUE_DEPTH)
        self._worker_task: asyncio.Task | None = None

        from ..adapters.router import ModelRouter
        def on_model_fallback(error_msg: str):
            asyncio.create_task(self.send_ws_message({
                "type": "model_fallback",
                "error": error_msg
            }))
        self._fallback_listener = on_model_fallback
        ModelRouter.register_fallback_listener(self._fallback_listener)

    def __del__(self):
        try:
            from ..adapters.router import ModelRouter
            ModelRouter.unregister_fallback_listener(self._fallback_listener)
        except Exception:
            pass

    async def monitor_and_stream_events(self, proc) -> None:
        """Stream process stdout events to the WebSocket client."""
        while proc and proc.status == "running":
            await asyncio.sleep(0.5)
            if getattr(proc, "localhost_url", None):
                await self.send_ws_message({
                    "type": "server_started",
                    "url": proc.localhost_url,
                    "port": proc.port,
                    "pid": proc.pid,
                    "status": proc.status,
                })
                break

    async def enqueue_message(self, text: str, mode: str, auto_apply: bool = False):
        """Queue a user message for sequential processing.

        If the queue is full a 'queue_full' WS event is sent and the message
        is dropped rather than silently overwriting in-flight work.
        """
        if self._message_queue.full():
            await self.send_ws_message({
                "type": "queue_full",
                "content": "âš ï¸ Request queue is full. Please wait for current tasks to complete before sending more messages.",
                "queue_depth": self._message_queue.qsize(),
            })
            return

        await self._message_queue.put((text, mode, auto_apply))

        # Emit queue depth so the frontend can show a badge
        await self.send_ws_message({
            "type": "queue_status",
            "queue_depth": self._message_queue.qsize(),
        })

        # Ensure the worker is running
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._queue_worker())

    async def _queue_worker(self):
        """Drain the message queue sequentially — one message at a time."""
        while not self._message_queue.empty():
            got_item = False
            try:
                text, mode, auto_apply = await self._message_queue.get()
                got_item = True
            except asyncio.CancelledError:
                break

            if got_item:
                try:
                    # Notify frontend that we're starting this item
                    await self.send_ws_message({
                        "type": "queue_status",
                        "queue_depth": self._message_queue.qsize(),
                    })
                    self.active_task = asyncio.current_task()
                    await self.handle_user_message(text, mode, auto_apply)
                except asyncio.CancelledError:
                    # Queue was cleared via cancel — stop worker silently
                    break
                except Exception as e:
                    logger.error(f"Queue worker error: {e}")
                finally:
                    self._message_queue.task_done()

        # Emit final queue-empty status
        await self.send_ws_message({
            "type": "queue_status",
            "queue_depth": 0,
        })

    async def cancel_all(self):
        """Cancel the current task and flush the entire pending queue."""
        # 1. Drain the queue so the worker won't pick up stale messages
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
                self._message_queue.task_done()
            except Exception:
                break

        # 2. Cancel the worker task
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # 3. Cancel the active handle_user_message task if running separately
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()

        # Propagate cancellation to canonical AgentRuntime
        if hasattr(self, "agent_runtime") and self.agent_runtime:
            await self.agent_runtime.cancel(self.session_id)

        # 4. B2: Clear pending confirmations so stale events cannot fire on
        #    the next request. Any tool awaiting confirmation will be cancelled
        #    by task cancellation above; the dict entry is now removed cleanly.
        self.pending_confirmations.clear()

        # 5. B6: Cancel any orphaned process-monitor background tasks.
        for t in list(self._monitor_tasks):
            if not t.done():
                t.cancel()
        # 6. Reset per-run state flags so they fire correctly on the next request.
        self._cost_advisory_sent = False

        await self.send_ws_message({
            "type": "queue_status",
            "queue_depth": 0,
        })

    async def load_history_from_db(self):
        try:
            from ..db import async_session, SessionModel
            from sqlalchemy.future import select
            from sqlalchemy.orm import selectinload
            async with async_session() as db:
                stmt = select(SessionModel).options(selectinload(SessionModel.messages)).where(SessionModel.id == self.session_id)
                res = await db.execute(stmt)
                session_obj = res.scalar()
                if session_obj:
                    if session_obj.mode:
                        self.last_mode = session_obj.mode
                    raw_history = []
                    for m in (session_obj.messages or []):
                        raw_content = m.content
                        content = ""
                        tool_calls = None
                        tool_call_id = None
                        tool_name = None
                        try:
                            if raw_content:
                                parsed = json.loads(raw_content)
                                if isinstance(parsed, dict) and "tool_calls" in parsed:
                                    tool_calls = parsed.get("tool_calls")
                                    content = str(parsed.get("content") or "")
                                elif isinstance(parsed, dict) and "tool_call_id" in parsed:
                                    tool_call_id = parsed.get("tool_call_id")
                                    tool_name = parsed.get("name")
                                    content = str(parsed.get("content") or "")
                                elif isinstance(parsed, str):
                                    content = parsed
                                elif parsed is None:
                                    content = ""
                                else:
                                    content = json.dumps(parsed)
                        except Exception:
                            content = raw_content or ""

                        entry: dict = {"role": m.role, "content": content}
                        if tool_calls:
                            entry["tool_calls"] = tool_calls
                        if tool_call_id:
                            entry["tool_call_id"] = tool_call_id
                            entry["name"] = tool_name or "unknown"
                        if m.role == "tool" and not entry.get("tool_call_id"):
                            entry["tool_call_id"] = "legacy_tool"
                            entry["name"] = entry.get("name", "unknown")
                        raw_history.append(entry)

                    # Fallback to messages_json if relational table has fewer messages or lacks assistant replies
                    has_assistant = any(m.get("role") in ("assistant", "tool") for m in raw_history)
                    if (not raw_history or not has_assistant) and session_obj.messages_json:
                        try:
                            json_msgs = json.loads(session_obj.messages_json)
                            if isinstance(json_msgs, list) and json_msgs:
                                raw_history = json_msgs
                        except Exception:
                            pass

                    self.conversation_history = raw_history
                    self._db_saved_up_to = len(raw_history)
        except Exception as e:
            logger.error(f"Failed to load history from DB: {e}")

    async def save_history_to_db(self):
        try:
            from ..db import async_session, SessionModel, MessageModel
            from sqlalchemy.future import select
            import json
            import datetime

            async with async_session() as db:
                async with db.begin():
                    stmt = select(SessionModel).where(SessionModel.id == self.session_id)
                    res = await db.execute(stmt)
                    session_obj = res.scalar()
                    if not session_obj:
                        from ..db import create_new_session_record
                        session_obj = await create_new_session_record(
                            db,
                            session_id=self.session_id,
                            title="Default Conversation",
                            workspace_root=self.workspace_root or "",
                            mode=self.last_mode or "Ask",
                        )
                        await db.flush()

                    # Query existing message sequences in the database for idempotency
                    msg_stmt = select(MessageModel.sequence).where(MessageModel.conversation_id == self.session_id)
                    msg_res = await db.execute(msg_stmt)
                    existing_seqs = set(msg_res.scalars().all())

                    for i, m in enumerate(self.conversation_history):
                        seq = i + 1
                        if seq in existing_seqs:
                            continue

                        role = m.get("role", "user")
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

                        msg = MessageModel(
                            conversation_id=self.session_id,
                            role=role,
                            content=db_content,
                            sequence=seq,
                            created_at=datetime.datetime.utcnow()
                        )
                        db.add(msg)
                        existing_seqs.add(seq)

                    self._db_saved_up_to = len(self.conversation_history)
                    session_obj.updated_at = datetime.datetime.utcnow()
                    if getattr(self, "workspace_root", None) is not None:
                        session_obj.workspace_root = self.workspace_root or ""
                    if getattr(self, "last_mode", None):
                        session_obj.mode = self.last_mode
                    try:
                        session_obj.messages_json = json.dumps(self.conversation_history)
                    except (TypeError, ValueError):
                        pass
        except Exception as e:
            logger.error(f"Failed to auto-save history to DB: {e}")

    def log_audit(self, tool_name: str, arguments: dict, status: str, details: str = ""):
        log_entry = {
            "tool": tool_name,
            "arguments": arguments,
            "status": status,
            "details": details
        }
        self.audit_log.append(log_entry)
        logger.info(f"Audit Log: {json.dumps(log_entry)}")

    def _trim_history_for_context(
        self,
        history: list,
        system_prompt: str = "",
        tools: list = None,
        max_chars: int | None = None
    ) -> list:
        """
        Trims conversation history using priority-aware budget allocation.
        """
        from ..context_config import HISTORY_MAX_CHARS
        from ..context_helpers import estimate_text_size, truncate_text
        
        limit = max_chars or HISTORY_MAX_CHARS
        reserved_for_next_prompt_chars = 50000
        effective_budget = max(limit - reserved_for_next_prompt_chars, 10000)
        
        tools_chars = len(json.dumps(tools or []))
        system_chars = len(system_prompt or "")
        budget = max(effective_budget - system_chars - tools_chars, 5000)
        
        if not history:
            return []
            
        total_len = len(history)
        
        # Identify special indices
        last_user_idx = -1
        last_assistant_idx = -1
        for idx in range(total_len - 1, -1, -1):
            msg = history[idx]
            r = msg.get("role", "")
            if r == "user" and last_user_idx == -1:
                last_user_idx = idx
            if r == "assistant" and last_assistant_idx == -1:
                last_assistant_idx = idx
                
        recent_threshold = max(0, total_len - 10)
        
        def get_priority(msg: dict, idx: int) -> int:
            role = msg.get("role", "")
            content = str(msg.get("content", "")).lower()
            
            if role in ("system", "developer"):
                return 1000
            if idx == last_user_idx:
                return 900
            
            if role == "user":
                if any(kw in content for kw in ("confirm", "approve", "reject", "yes", "no", "apply", "cancel")):
                    return 850
                    
            if idx == last_assistant_idx:
                return 800
                
            is_error = msg.get("status") == "error" or "error" in content or "failed" in content
            if is_error and idx >= recent_threshold:
                return 750
                
            if idx >= recent_threshold:
                return 650
                
            if "[summary" in content or "[prior steps" in content:
                return 500
                
            if role == "tool":
                return 300
                
            return 100

        scored_messages = []
        for idx, msg in enumerate(history):
            prio = get_priority(msg, idx)
            size = self._msg_size_cache.get(idx)
            if size is None:
                size = estimate_text_size(msg)
                self._msg_size_cache[idx] = size
            scored_messages.append((prio, idx, msg, size))
            
        sorted_candidates = sorted(scored_messages, key=lambda x: (x[0], x[1]), reverse=True)
        
        retained_indices = set()
        current_used = 0
        truncated_msg_contents = {}
        
        for prio, idx, msg, size in sorted_candidates:
            is_protected = prio >= 800
            
            if is_protected:
                retained_indices.add(idx)
                if current_used + size > budget:
                    content_str = str(msg.get("content", ""))
                    truncated_content = truncate_text(content_str, 50000, label=f"message {idx}")
                    truncated_msg_contents[idx] = truncated_content
                    current_used += estimate_text_size({"role": msg.get("role"), "content": truncated_content})
                else:
                    current_used += size
            else:
                if current_used + size <= budget:
                    retained_indices.add(idx)
                    current_used += size
                elif current_used < budget:
                    content_str = str(msg.get("content", ""))
                    remaining_space = budget - current_used
                    if remaining_space > 2000:
                        retained_indices.add(idx)
                        truncated_content = truncate_text(content_str, remaining_space - 1000, label=f"message {idx}")
                        truncated_msg_contents[idx] = truncated_content
                        current_used += estimate_text_size({"role": msg.get("role"), "content": truncated_content})
                        
        trimmed_history = []
        last_was_trim_marker = False
        
        for idx in range(total_len):
            if idx in retained_indices:
                msg = history[idx]
                if idx in truncated_msg_contents:
                    msg_copy = dict(msg)
                    msg_copy["content"] = truncated_msg_contents[idx]
                    trimmed_history.append(msg_copy)
                else:
                    trimmed_history.append(msg)
                last_was_trim_marker = False
            else:
                if not last_was_trim_marker:
                    trimmed_history.append({
                        "role": "user",
                        "content": "[System Note: Older low-priority history entries truncated to preserve context budget]"
                    })
                    last_was_trim_marker = True
                    
        return trimmed_history

    def _extract_tool_call_from_text(self, text: str) -> dict | None:
        """Fallback parser to extract tool calls formatted as plain JSON in the text response."""
        if not text:
            return None
        clean_text = text.strip()
        
        # Remove markdown code fences if present
        if clean_text.startswith("```"):
            lines = clean_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()
            
        def _normalize_tool_dict(data: dict) -> dict | None:
            name = data.get("name") or data.get("function_name") or data.get("function")
            args = data.get("arguments") or data.get("input") or data.get("parameters")
            if name and isinstance(name, str) and (args is not None or "agent_name" in data or "task_description" in data):
                if args is None:
                    args = {k: v for k, v in data.items() if k not in ("name", "function_name", "function", "type")}
                return {"name": name, "arguments": args, "input": args}
            return None

        try:
            data = json.loads(clean_text)
            if isinstance(data, dict):
                norm = _normalize_tool_dict(data)
                if norm:
                    return norm
        except Exception:
            pass
            
        # Regex fallback for embedded JSON object
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    norm = _normalize_tool_dict(data)
                    if norm:
                        return norm
            except Exception:
                pass
        return None

    def _get_adapter(self, is_agent: bool = False):
        from ..adapters.router import ModelRouter
        from ..state import config_manager
        latest_profile = config_manager.get_active_profile() or self.profile
        router = ModelRouter()
        return router.get_adapter(latest_profile, is_agent=is_agent)

    def _get_tools_for_mode(self, mode: str) -> list:
        read_only_tools = {
            "list_directory", "read_file", "search_codebase",
            "open_with_live_server", "glob", "todo_read",
        }
        all_agent_tools = {
            t["name"] for t in AVAILABLE_TOOLS
        }
        if mode in ("Ask", "Plan"):
            return [t for t in AVAILABLE_TOOLS if t["name"] in read_only_tools]
        elif mode == "Agent":
            return AVAILABLE_TOOLS
        else:
            # Edit mode: everything except delegation
            return [t for t in AVAILABLE_TOOLS if t["name"] != "delegate_to_agent"]


    def _get_system_prompt(self, mode: str) -> str:
        """Build the system prompt for the given operating mode.

        Args:
            mode: Ask, Plan, or Agent.

        Returns:
            Fully rendered master system prompt, including relevant skills.md.
        """
        # ── System-prompt cache (mtime-keyed) ────────────────────────────────
        # Rebuilding the full prompt involves os.walk, build_skills_prompt_section,
        # and render_system_prompt on every LLM turn — expensive on large repos.
        # Cache the result keyed by workspace mtime; invalidate when files change.
        current_mtime: float = 0.0
        if self.workspace_root and os.path.isdir(self.workspace_root):
            try:
                current_mtime = os.path.getmtime(self.workspace_root)
            except OSError:
                pass
        cached = self._cached_system_prompt.get(mode)
        if cached and cached[0] == current_mtime and current_mtime > 0:
            return cached[1]

        workspace_context = ""

        from ..workspace_index import WorkspaceIndex
        try:
            # B9: Reuse the cached WorkspaceIndex instance across turns.
            # Creating a new instance on every LLM call discards the mtime cache
            # and triggers a full os.walk on the workspace each turn.
            if self._workspace_index is None:
                self._workspace_index = WorkspaceIndex.get_instance(self.workspace_root)
            context = self._workspace_index.get_prompt_context(max_tokens=800)
            if context:
                workspace_context = context
        except Exception as e:
            logger.error(f"Failed to load workspace context: {e}")
            self._workspace_index = None  # reset so it retries next turn

        skills_section = ""
        try:
            from ..skills_loader import build_skills_prompt_section
            skills_section = build_skills_prompt_section(
                self.workspace_root,
                languages=getattr(self, "open_languages", None) or None,
                open_files=getattr(self, "open_files", None) or None,
            )
        except Exception as e:
            logger.warning(f"Failed to load workspace skills: {e}")

        max_orchestrator_steps = getattr(self.orchestrator, "max_steps", 30)

        # Choose the right mode instructions block
        if mode == "Ask":
            mode_instructions = ASK_MODE_INSTRUCTIONS
            agent_orchestration_section = ""  # No orchestration noise in Ask mode
        elif mode == "Plan":
            mode_instructions = PLAN_MODE_INSTRUCTIONS
            agent_orchestration_section = ""  # No orchestration noise in Plan mode
        else:  # Agent
            mode_instructions = AGENT_MODE_INSTRUCTIONS.replace(
                "{max_orchestrator_steps}", str(max_orchestrator_steps)
            )
            # Build agent list from orchestrator
            try:
                agent_list = ", ".join(self.orchestrator.agents.keys())
            except Exception:
                agent_list = "See orchestrator configuration"
            agent_orchestration_section = AGENT_ORCHESTRATION_SECTION.replace(
                "{agent_list}", agent_list
            )
            
            # Format and append collaboration log
            if hasattr(self.orchestrator, "context") and self.orchestrator.context:
                if getattr(self.orchestrator.context, "collaboration_log", None):
                    log_entries = "\n".join(f"- {entry}" for entry in self.orchestrator.context.collaboration_log)
                    agent_orchestration_section += f"\n\nCollaboration Log:\n{log_entries}"
                if getattr(self.orchestrator.context, "memory", None):
                    from ..context_helpers import build_memory_summary
                    memory_summary = build_memory_summary(self.orchestrator.context.memory, indent=2)
                    agent_orchestration_section += f"\n\nShared Memory:\n{memory_summary}"

        prompt = render_system_prompt(
            workspace_root=self.workspace_root,
            mode=mode,
            workspace_context=workspace_context,
            mode_instructions=mode_instructions,
            agent_orchestration_section=agent_orchestration_section,
        )
        if skills_section:
            prompt = prompt.rstrip() + "\n\n" + skills_section

        # Store in cache for subsequent turns (invalidated when workspace mtime changes)
        if current_mtime > 0:
            self._cached_system_prompt[mode] = (current_mtime, prompt)

        return prompt

    async def _run_agent_intelligence_pipeline(self, text: str, base_system_prompt: str) -> str:
        """Run all 14-phase intelligence modules and enrich the system prompt.

        Phases executed (in order):
          Phase 5  — Intent Router: classify intent
          Phase 1  — Context Collector: auto-read files/specs
          Phase 2  — Planning Engine: generate task graph
          Phase 10 — Workflow Engine: emit tool sequence hints
          Phase 11 — Tool Policy: inject tool rules
          Phase 7  — Confidence Scorer: detect context gaps
          Phase 13 — Execution Logger: start logging
          Phase 4  — Task Memory: reset or resume state

        Returns enriched system prompt with all context blocks appended.
        """
        try:
            # ── Phase 5: Intent Router ──────────────────────────────────
            intent_result = self._intent_router.classify(text, last_mode=self.last_mode)
            self._current_intent = intent_result.intent
            logger.info(
                f"[IntentRouter] '{text[:60]}' → {intent_result.intent.value} "
                f"(conf={intent_result.confidence:.0%})"
            )

            # ── Phase 13: Start Execution Logger ───────────────────────
            self._exec_logger = ExecutionLogger(self.session_id)
            self._exec_logger.set_intent(intent_result.intent.value, goal=text)

            # ── Phase 4: Task Memory — reset or resume ─────────────────
            if intent_result.intent == IntentType.CONTINUE and self.task_memory.steps:
                # Resume existing task — do NOT reset
                logger.info("[TaskMemory] Resuming previous task.")
            else:
                self.task_memory.reset(goal=text, intent=intent_result.intent.value)

            # ── Phase 1: Context Collector ──────────────────────────────
            collected_ctx = None
            # Check if last 6 messages already contain tool results
            has_recent_tool_results = False
            for msg in self.conversation_history[-6:]:
                if msg.get("role") == "tool" or (msg.get("role") == "assistant" and msg.get("tool_calls")):
                    has_recent_tool_results = True
                    break

            if intent_result.needs_context and not has_recent_tool_results:
                await self.send_ws_message({
                    "type": "status",
                    "status": "thinking",
                    "message": "Collecting workspace context...",
                })
                try:
                    collected_ctx = await self._context_collector.collect(
                        user_query=text,
                        referenced_files=intent_result.referenced_files,
                        referenced_symbols=intent_result.referenced_symbols,
                        spec_file=intent_result.spec_file,
                    )
                    # Log context files
                    for f in collected_ctx.files_read:
                        self._exec_logger.record_context_file(f)
                        self.task_memory.record_read(f)
                    if collected_ctx.spec_content and intent_result.spec_file:
                        self._exec_logger.record_context_file(intent_result.spec_file)
                        self.task_memory.record_read(intent_result.spec_file)

                    logger.info(
                        f"[ContextCollector] Read {len(collected_ctx.files_read)} files, "
                        f"found {len(collected_ctx.symbols_found)} symbols."
                    )
                except Exception as cc_err:
                    logger.warning(f"[ContextCollector] Error (non-fatal): {cc_err}")

            # ── Phase 7: Confidence Scorer ──────────────────────────────
            tech_stack_known = bool(
                collected_ctx and (collected_ctx.config_hints or collected_ctx.manifest_content)
            ) if collected_ctx else False

            spec_file_read = bool(
                collected_ctx and collected_ctx.spec_content
            ) if collected_ctx else False

            workspace_non_empty = bool(
                collected_ctx and collected_ctx.workspace_structure
            ) if collected_ctx else True  # Assume non-empty if collector not run

            confidence = self._confidence_scorer.score(
                intent=intent_result.intent,
                referenced_files=intent_result.referenced_files,
                resolved_files=list(collected_ctx.files_read.keys()) if collected_ctx else [],
                tech_stack_known=tech_stack_known,
                spec_file_read=spec_file_read,
                workspace_non_empty=workspace_non_empty,
                query_length=len(text),
                symbols_found=collected_ctx.symbols_found if collected_ctx else {},
                referenced_symbols=intent_result.referenced_symbols,
            )
            logger.info(
                f"[ConfidenceScorer] score={confidence.score:.0%} → {confidence.action}"
            )

            # ── Phase 2: Planning Engine ────────────────────────────────
            plan = None
            if intent_result.needs_plan:
                workspace_has_files = workspace_non_empty
                plan = self._planning_engine.generate(
                    goal=text,
                    intent=intent_result.intent,
                    referenced_files=intent_result.referenced_files,
                    spec_file=intent_result.spec_file,
                    workspace_has_files=workspace_has_files,
                )
                if plan.steps:
                    self.task_memory.set_steps(plan.steps)
                    self._exec_logger.set_plan(plan.steps)
                    logger.info(
                        f"[PlanningEngine] Generated {len(plan.steps)}-step plan "
                        f"for {intent_result.intent.value}."
                    )

            # ── Phase 10: Workflow Engine ───────────────────────────────
            workflow_ctx = self._workflow_engine.get_workflow(
                intent=intent_result.intent,
                task_memory=self.task_memory,
            )

            # ── Phase 11: Tool Policy ───────────────────────────────────
            tool_policy_block = self._tool_policy.to_prompt_block(intent_result.intent)

            # ── Assemble enriched system prompt ─────────────────────────
            extra_sections = []

            # Task memory resume section (for CONTINUE)
            if intent_result.intent == IntentType.CONTINUE and self.task_memory.steps:
                extra_sections.append(
                    "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "TASK MEMORY — RESUMING PREVIOUS TASK\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    + self.task_memory.to_summary_prompt()
                )

            # Collected context
            if collected_ctx:
                ctx_block = collected_ctx.to_prompt_block()
                if ctx_block:
                    extra_sections.append(ctx_block)

            # Workflow hints
            wf_block = workflow_ctx.to_prompt_block()
            if wf_block:
                extra_sections.append(wf_block)

            # Plan
            if plan and plan.steps:
                extra_sections.append(plan.to_prompt_block())

            # Tool policy
            if tool_policy_block:
                extra_sections.append(tool_policy_block)

            # Confidence gap warning
            if confidence.action in ("collect_more", "ask_user"):
                conf_block = self._confidence_scorer.to_prompt_block(confidence)
                if conf_block:
                    extra_sections.append(conf_block)

            enriched_prompt = base_system_prompt
            for section in extra_sections:
                enriched_prompt = enriched_prompt.rstrip() + "\n" + section

            return enriched_prompt

        except Exception as e:
            logger.warning(f"[AgentIntelligencePipeline] Error (non-fatal, using base prompt): {e}")
            return base_system_prompt

    async def handle_user_message(self, text: str, mode: str, auto_apply: bool = False):
        """
        Runs the agent loop for a user query.
        """

        self.auto_apply = auto_apply
        if self.is_running:
            import time
            _stuck_since = getattr(self, "_running_since", None)
            _now = time.monotonic()
            if _stuck_since is None or (_now - _stuck_since) > 90:
                self.is_running = False
                self.pending_confirmations.clear()
            else:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "\n[Agent is already running. Please wait or click Stop to cancel.]\n"
                })
                await self.send_ws_message({
                    "type": "session_done",
                    "total_cost_usd": getattr(self, "total_cost_usd", 0.0)
                })
                return

        # Store snapshot at the start of handle_user_message
        self._last_request_snapshot = {
            "text": text,
            "mode": mode,
            "auto_apply": auto_apply,
            "history": list(self.conversation_history)
        }

        # Check for contradiction first
        contradiction = detect_contradiction(text)
        if contradiction:
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"\n\n[WARNING] **Contradictory Instructions Detected**:\n{contradiction}"
            })
            await self.send_ws_message({
                "type": "session_done",
                "total_cost_usd": self.total_cost_usd,
                "wasted_turns": getattr(self, "wasted_turns", 0),
            })
            return

        import time
        self._running_since = time.monotonic()
        self.is_running = True
        try:
            # Append user request to history
            self.conversation_history.append({"role": "user", "content": text})

            # Auto-route mode selection if set to 'Auto'
            if mode == "Auto":
                if getattr(self, "last_mode", None) == "Agent" and len(text.strip()) < 30:
                    mode = "Agent"
                    logger.info(f"Auto-inherited Agent mode for short follow-up: '{text[:40]}'")

            if mode == "Auto":
                # â”â” Fast-path router: classify trivial inputs without an LLM call â”â”
                _t = text.strip().lower().rstrip("!?.,:;")

                # â”â” Greeting / ack fast-path â” no LLM call needed â”â”
                _GREETINGS = {
                    "hi", "hello", "hey", "yo", "sup", "hiya", "howdy", "greetings",
                    "thanks", "thank you", "ty", "thx", "cheers",
                    "ok", "okay", "yes", "no", "sure", "cool", "got it",
                    "alright", "great", "perfect", "good", "nice", "awesome",
                    "sounds good", "makes sense", "make sense",
                }
                if _t in _GREETINGS:
                    mode = "Ask"

                # â”â” Very short non-action input â†’ Ask â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
                elif len(_t) < 12 and not any(
                    kw in _t for kw in [
                        "create", "write", "fix", "run", "build",
                        "add", "edit", "delete", "install", "refactor",
                    ]
                ):
                    mode = "Ask"

                # â”â” Explicit action keywords â†’ Agent (no LLM call) â”â”â”â”â”â”â”
                elif re.search(
                    r'\b(create|write|build|fix|run|start|launch|install|'
                    r'refactor|edit|delete|add|generate|deploy|implement|'
                    r'scaffold|init|setup|migrate|seed)\b',
                    _t,
                ):
                    mode = "Agent"

                # â”â” Question-word fast-path â†’ Ask (no LLM call) â”â”â”â”â”â”â”â”â”â”
                elif re.match(
                    r'^(what|why|how|when|where|who|which|explain|describe|'
                    r'tell me|can you tell|show me how|what is|what are|'
                    r'what does|how does|how do)\b',
                    _t,
                ):
                    mode = "Ask"

                # â”â” Genuinely ambiguous â” call LLM classifier â”â”â”â”â”â”â”â”â”â”â”â”
                else:
                    _CLASSIFIER_PROMPT = (
                        "You are a query classifier for a coding IDE. "
                        "Read the user's message and return EXACTLY one word: Ask, Plan, or Agent.\n\n"
                        "RULES:\n"
                        "  Ask   â†’ Greetings, questions, explanations, definitions, code review without changes.\n"
                        "  Plan  â†’ User explicitly wants a plan, outline, or roadmap WITHOUT implementation.\n"
                        "  Agent â†’ User wants ACTIONS: create files, edit code, fix bugs, run commands, write tests.\n\n"
                        "EXAMPLES:\n"
                        "  what is a decorator           â†’ Ask\n"
                        "  review this code              â†’ Ask\n"
                        "  plan a REST API               â†’ Plan\n"
                        "  design the database schema    â†’ Plan\n"
                        "  create a login page           â†’ Agent\n"
                        "  fix the bug in auth.py        â†’ Agent\n\n"
                        "Reply with ONLY one word. No punctuation. No explanation."
                    )
                    try:
                        response = await self._run_llm_query(
                            _CLASSIFIER_PROMPT, text, agent_name="Router"
                        )
                        classified = response.strip().strip("'\"").rstrip(".").strip()
                        if classified in ("Ask", "Plan", "Agent"):
                            mode = classified
                        elif "ask" in classified.lower():
                            mode = "Ask"
                        elif "plan" in classified.lower():
                            mode = "Plan"
                        elif "agent" in classified.lower():
                            mode = "Agent"
                        else:
                            mode = "Ask"  # Safe fallback â” never default to Agent
                    except Exception as e:
                        logger.error(f"Auto-classifier LLM call failed: {e}")
                        mode = "Ask"  # Safe fallback
                logger.info(f"Auto-routed '{text[:60]}' â†’ mode={mode}")

            self.last_mode = mode

            if mode == "Agent":
                # Run the 14-phase intelligence pipeline first, then fall through
                # to the direct tool-calling loop below — do NOT short-circuit.
                pass  # pipeline runs below at the ── 14-Phase ── block

            # Unified tool-calling loop — runs for ALL modes (Ask, Plan, Agent, Goal).
            # Mode-specific behaviour is controlled by tools list and system prompt, not the loop itself.
            adapter = self._get_adapter(is_agent=(mode in ("Agent", "Goal")))
            system_prompt = self._get_system_prompt(mode)
            tools = self._get_tools_for_mode(mode)

            # ── 14-Phase Agent Intelligence Layer (Agent mode only) ───────
            if mode == "Agent":
                _cached_enriched_prompt: dict[str, str] = {}

                async def agent_llm_provider(messages: list, tools_schema: list):
                    cache_key = text  # same user message across all turns
                    if cache_key not in _cached_enriched_prompt:
                        sys_prompt = self._get_system_prompt("Agent")
                        sys_prompt = await self._run_agent_intelligence_pipeline(
                            text, sys_prompt
                        )
                        _cached_enriched_prompt[cache_key] = sys_prompt
                    else:
                        sys_prompt = _cached_enriched_prompt[cache_key]

                    # Determine step number from messages list length
                    step_num = len(messages) // 2 + 1

                    # Send status update
                    await self.send_ws_message({
                        "type": "status",
                        "status": "generating_code",
                        "message": f"Agent turn {step_num}...",
                        "mode": "Agent",
                    })

                    response_text = ""
                    tool_calls_to_run = []
                    thinking_blocks_current_turn = []

                    trimmed_history = self._trim_history_for_context(
                        messages, sys_prompt, tools
                    )
                    async for chunk in self._stream_chat_wrapper(adapter, trimmed_history, tools, sys_prompt):
                        if chunk["type"] == "text":
                            response_text += chunk["content"]
                            await self.send_ws_message({
                                "type": "text_delta",
                                "content": chunk["content"]
                            })
                        elif chunk["type"] == "tool_call":
                            tool_calls_to_run.append(chunk)
                        elif chunk["type"] == "thinking":
                            thinking_blocks_current_turn.append({
                                "type": "thinking",
                                "thinking": chunk.get("thinking", ""),
                                "signature": chunk.get("signature"),
                            })
                            await self.send_ws_message({
                                "type": "thinking",
                                "content": chunk.get("thinking", ""),
                                "signature": chunk.get("signature"),
                            })
                        elif chunk["type"] == "redacted_thinking":
                            thinking_blocks_current_turn.append({
                                "type": "redacted_thinking",
                                "data": chunk.get("data", ""),
                            })
                            await self.send_ws_message({
                                "type": "thinking",
                                "content": chunk.get("data", "") or "Thinking...",
                                "signature": "redacted",
                            })

                    # Form raw tool calls list for AgentRuntime normalizer
                    import json
                    raw_tool_calls = []
                    for tc in tool_calls_to_run:
                        raw_tool_calls.append({
                            "id": tc["id"],
                            "name": tc["name"],
                            "arguments": json.dumps(tc["input"]) if isinstance(tc["input"], dict) else tc["input"]
                        })

                    # Record assistant message in the conversation history
                    assistant_msg = {
                        "role": "assistant",
                        "content": response_text
                    }
                    if thinking_blocks_current_turn:
                        assistant_msg["thinking_blocks"] = thinking_blocks_current_turn
                    if tool_calls_to_run:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": tc["input"],
                                "thought_signature": tc.get("thought_signature")
                            }
                            for tc in tool_calls_to_run
                        ]
                    self.conversation_history.append(assistant_msg)

                    if self._exec_logger:
                        self._exec_logger.increment_turns()
                    self._agent_tool_call_count += len(tool_calls_to_run)

                    if not response_text.strip() and not tool_calls_to_run:
                        logger.error("LLM returned an empty response with no content and no tool calls.")
                        raise RuntimeError("LLM returned an empty response with no content and no tool calls.")

                    return {
                        "content": response_text,
                        "tool_calls": raw_tool_calls
                    }

                effective_max_turns = self.max_turns
                self._agent_tool_call_count = 0

                run_res = await self.agent_runtime.run(
                    session_id=self.session_id,
                    task=text,
                    mode="Agent",
                    auto_apply=auto_apply,
                    max_turns=effective_max_turns,
                    llm_provider_func=agent_llm_provider,
                    agent_session=self
                )

                # Set task memory files written
                self.task_memory.files_written = list(
                    set(run_res.changed_files.get("created_files", [])) |
                    set(run_res.changed_files.get("modified_files", []))
                )
                
                # Parse diffs for file edits count (+adds -removes)
                diffs = run_res.changed_files.get("diffs", {})
                file_edits = {}
                for fpath, diff_content in diffs.items():
                    added = 0
                    removed = 0
                    if diff_content:
                        for line in diff_content.splitlines():
                            if line.startswith("+++") or line.startswith("---"):
                                continue
                            if line.startswith("+"):
                                added += 1
                            elif line.startswith("-"):
                                removed += 1
                    file_edits[fpath] = {"added": added, "removed": removed}
                self.task_memory.file_edits = file_edits

                # Verification results
                _verification_evidence = None
                if run_res.verification_status != "NOT_RUN" and self.task_memory.files_written:
                    try:
                        await self.send_ws_message({
                            "type": "status",
                            "status": "verifying",
                            "message": "Verifying changes...",
                        })
                        from ..agent.agent_runtime.verification import VerificationEngine
                        _ve = VerificationEngine(self.workspace_root, timeout=60.0)
                        _vr = await _ve.verify()
                        _verification_evidence = _vr.to_evidence()
                        await self.send_ws_message({
                            "type": "verification_result",
                            "passed": _vr.passed,
                            "summary": _vr.summary,
                            "checks": _verification_evidence.get("checks", []),
                        })
                    except Exception as ve_err:
                        logger.warning(f"VerificationEngine error (non-fatal): {ve_err}")

                if self._exec_logger:
                    self._exec_logger.set_cost(getattr(self, "total_cost_usd", 0.0))
                    self._exec_logger.finish("completed" if run_res.success else "failed")
                    self._exec_logger.emit()

                await self.send_ws_message({
                    "type": "session_done",
                    "total_cost_usd": getattr(self, "total_cost_usd", 0.0),
                    "wasted_turns": getattr(self, "wasted_turns", 0),
                    "task_memory": self.task_memory.to_dict(),
                    "verification": _verification_evidence,
                })

            else:
                effective_max_turns = self.max_turns
                # B1: Previously 10000 in Agent mode, which could run API costs into
                # hundreds of dollars silently. Now capped at max_turns*4 (ceiling 200).
                turn = 0
                self._agent_tool_call_count = 0  # reset per-run counter

                def _tool_stage(tc_name: str) -> str:
                    """Map a tool name to a UI progress stage status code."""
                    _READ_TOOLS = (
                        "list_directory", "list_files", "list_dir", "ls",
                        "read_file", "view_file", "get_file", "open_file",
                        "search_codebase", "search_files", "search_code", "grep",
                        "glob", "glob_search",
                    )
                    _WRITE_TOOLS = (
                        "write_file", "create_file", "write_to_file", "save_file",
                        "edit_file", "apply_patch", "patch",
                    )
                    _VALIDATE_TOOLS = ("run_terminal_command", "execute_command", "run_command",)
                    n = tc_name.lower()
                    if n in _READ_TOOLS:
                        return "reading_workspace"
                    if n in _WRITE_TOOLS:
                        return "writing_files"
                    if n in _VALIDATE_TOOLS:
                        return "validating"
                    return "tool_executing"

                while turn < effective_max_turns:
                    turn += 1

                    # Send mode-aware status update
                    _status_msg = (
                        "Thinking..."
                        if mode == "Ask"
                        else f"Planning (turn {turn})..."
                        if mode == "Plan"
                        else f"Agent turn {turn}..."
                    )
                    await self.send_ws_message({
                        "type": "status",
                        "status": "generating_code" if mode == "Agent" else "thinking",
                        "message": _status_msg,
                        "mode": mode,
                    })

                    response_text = ""
                    tool_calls_to_run = []
                    thinking_blocks_current_turn: list = []  # A6: accumulate per-turn thinking blocks
                    if self._exec_logger:
                        self._exec_logger.increment_turns()

                    # 1. Stream the model's text response and collect tool calls
                    try:
                        # Trim history to fit within token budget before each API call
                        trimmed_history = self._trim_history_for_context(
                            self.conversation_history, system_prompt, tools
                        )
                        async for chunk in self._stream_chat_wrapper(adapter, trimmed_history, tools, system_prompt):
                            if chunk["type"] == "text":
                                response_text += chunk["content"]
                                await self.send_ws_message({
                                    "type": "text_delta",
                                    "content": chunk["content"]
                                })
                            elif chunk["type"] == "tool_call":
                                tool_calls_to_run.append(chunk)
                            elif chunk["type"] == "thinking":
                                # A6: capture thinking block for re-emission next turn
                                thinking_blocks_current_turn.append({
                                    "type": "thinking",
                                    "thinking": chunk.get("thinking", ""),
                                    "signature": chunk.get("signature"),
                                })
                                await self.send_ws_message({
                                    "type": "thinking",
                                    "content": chunk.get("thinking", ""),
                                    "signature": chunk.get("signature"),
                                })
                            elif chunk["type"] == "redacted_thinking":
                                # A6: capture redacted_thinking block
                                thinking_blocks_current_turn.append({
                                    "type": "redacted_thinking",
                                    "data": chunk.get("data", ""),
                                })
                                await self.send_ws_message({
                                    "type": "thinking",
                                    "content": chunk.get("data", "") or "Thinking...",
                                    "signature": "redacted",
                                })
                            elif chunk["type"] == "tool_call_error":
                                # A7: model produced malformed JSON surface as a tool result error
                                err_msg = chunk.get("error", "Unknown tool call error")
                                logger.warning(f"A7 tool_call_error: {err_msg}")
                                await self.send_ws_message({
                                    "type": "text_delta",
                                    "content": f"\n\n[WARNING] {err_msg}\n"
                                })
                            elif chunk["type"] == "usage":
                                pass
                            elif chunk["type"] == "done":
                                stop_reason = chunk["stop_reason"]
                    except Exception as e:
                        # Auto-retry with aggressively trimmed history on 413 (context too large)
                        err_str = str(e)
                        if "413" in err_str or "too large" in err_str.lower() or "tokens" in err_str.lower():
                            logger.warning(f"Context too large, retrying with trimmed history: {err_str}")
                            try:
                                trimmed_history = self._trim_history_for_context(
                                    self.conversation_history, system_prompt, tools,
                                    max_chars=6000  # Aggressive trim for small models
                                )
                                response_text = ""
                                tool_calls_to_run = []
                                async for chunk in self._stream_chat_wrapper(adapter, trimmed_history, tools, system_prompt):
                                    if chunk["type"] == "text":
                                        response_text += chunk["content"]
                                        await self.send_ws_message({
                                            "type": "text_delta",
                                            "content": chunk["content"]
                                        })
                                    elif chunk["type"] == "tool_call":
                                        tool_calls_to_run.append(chunk)
                                    elif chunk["type"] == "thinking":
                                        thinking_blocks_current_turn.append({
                                            "type": "thinking",
                                            "thinking": chunk.get("thinking", ""),
                                            "signature": chunk.get("signature"),
                                        })
                                        await self.send_ws_message({
                                            "type": "thinking",
                                            "content": chunk.get("thinking", ""),
                                            "signature": chunk.get("signature"),
                                        })
                                    elif chunk["type"] == "redacted_thinking":
                                        thinking_blocks_current_turn.append({
                                            "type": "redacted_thinking",
                                            "data": chunk.get("data", ""),
                                        })
                                        await self.send_ws_message({
                                            "type": "thinking",
                                            "content": chunk.get("data", "") or "Thinking...",
                                            "signature": "redacted",
                                        })
                                    elif chunk["type"] == "done":
                                        stop_reason = chunk["stop_reason"]
                            except Exception as retry_err:
                                raise retry_err
                        elif isinstance(e, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)) or "time" in err_str.lower() or "timeout" in err_str.lower() or "connecttimeout" in err_str.lower():
                            logger.error(f"Agent session API call timed out: {e}")
                            raise TimeoutError("API Request Timed Out") from e
                        else:
                            raise e


                    # Fallback: if no native tool calls were found, try to parse a JSON tool call from the response text.
                    if not tool_calls_to_run and response_text:
                        parsed_tc = self._extract_tool_call_from_text(response_text)
                        if parsed_tc:
                            tc_name = parsed_tc.get("name")
                            tc_input = parsed_tc.get("arguments") or parsed_tc.get("input") or {}
                            if tc_name:
                                import uuid
                                mock_id = f"call_{uuid.uuid4().hex[:8]}"
                                tool_calls_to_run.append({
                                    "type": "tool_call",
                                    "id": mock_id,
                                    "name": tc_name,
                                    "input": tc_input
                                })
                                # Clean response_text so we don't display raw JSON to user as text
                                if response_text.strip().startswith("{") and response_text.strip().endswith("}"):
                                    response_text = f"Calling tool `{tc_name}`..."

                    # 2. Append assistant response to history
                    assistant_msg = {
                        "role": "assistant",
                        "content": response_text
                    }
                    # A6: store thinking blocks so _to_anthropic_messages re-emits them next turn
                    if thinking_blocks_current_turn:
                        assistant_msg["thinking_blocks"] = thinking_blocks_current_turn

                    if tool_calls_to_run:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": tc["input"],
                                "thought_signature": tc.get("thought_signature")
                            }
                            for tc in tool_calls_to_run
                        ]

                    self.conversation_history.append(assistant_msg)

                    # If no tool calls, the turn loop is complete
                    if not tool_calls_to_run:
                        break

                    # 3. Execute tool calls (potentially seeking user confirmation)
                    tool_results = []
                
                    # Chunk tool_calls_to_run into batches. Safe read-only tools and 'delegate_to_agent'
                    # run concurrently using asyncio.gather, while mutating tools run sequentially.
                    PARALLEL_SAFE_TOOLS = {
                        "read_file", "list_dir", "search_files", "glob",
                        "grep", "get_file_info", "shared_memory_get",
                        "delegate_to_agent",
                    }
                    batches = []
                    current_batch = []
                    is_parallel_batch = False

                    for tc in tool_calls_to_run:
                        is_parallel = tc["name"] in PARALLEL_SAFE_TOOLS
                        if not current_batch:
                            current_batch.append(tc)
                            is_parallel_batch = is_parallel
                        else:
                            if is_parallel == is_parallel_batch and is_parallel_batch:
                                current_batch.append(tc)
                            else:
                                batches.append((current_batch, is_parallel_batch))
                                current_batch = [tc]
                                is_parallel_batch = is_parallel
                    if current_batch:
                        batches.append((current_batch, is_parallel_batch))

                    for batch, is_parallel in batches:
                        _wasted_signals = (
                            "timed out", "timeout",
                            "Action cancelled", "cancelled",
                            "Target block not found", "Edit failed",
                            "near-match was detected",
                            "differs starting at line",
                            "malformed JSON arguments",
                        )

                        if is_parallel:
                            # Run consecutive delegate_to_agent calls in parallel
                            async def run_single_tool(tc):
                                tc_id = tc["id"]
                                tc_name = tc["name"]
                                tc_args = tc["input"]

                                _stage = _tool_stage(tc_name)
                                await self.send_ws_message({
                                    "type": "status",
                                    "status": _stage,
                                    "message": f"{_stage.replace('_', ' ').title()}: {tc_name}...",
                                    "tool_call": {"id": tc_id, "name": tc_name, "args": tc_args}
                                })

                                if tc.get("error"):
                                    result = tc["error"]
                                    status = "error"
                                else:
                                    try:
                                        result = await self._execute_tool_with_guardrails(tc_id, tc_name, tc_args, auto_apply)
                                        status = "success"
                                    except Exception as e:
                                        result = f"Error executing tool '{tc_name}': {str(e)}"
                                        status = "error"

                                if any(sig.lower() in result.lower() for sig in _wasted_signals):
                                    if hasattr(self, "wasted_turns"):
                                        self.wasted_turns += 1

                                # Send result back to frontend for chat display
                                await self.send_ws_message({
                                    "type": "tool_result",
                                    "tool_call_id": tc_id,
                                    "name": tc_name,
                                    "status": status,
                                    "result": result
                                })

                                from ..context_helpers import prepare_tool_result_for_history
                                compact_result = prepare_tool_result_for_history(result, tool_name=tc_name)
                            
                                entry = {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": tc_name,
                                    "content": compact_result
                                }
                                if len(str(result)) > len(compact_result):
                                    entry["metadata"] = {
                                        "truncated": True,
                                        "original_chars": len(str(result)),
                                        "retained_chars": len(compact_result)
                                    }
                                return entry

                            results = await asyncio.gather(*(run_single_tool(tc) for tc in batch))
                            tool_results.extend(results)
                        else:
                            # Run sequentially
                            for tc in batch:
                                tc_id = tc["id"]
                                tc_name = tc["name"]
                                tc_args = tc["input"]

                                _stage = _tool_stage(tc_name)
                                await self.send_ws_message({
                                    "type": "status",
                                    "status": _stage,
                                    "message": f"{_stage.replace('_', ' ').title()}: {tc_name}...",
                                    "tool_call": {"id": tc_id, "name": tc_name, "args": tc_args}
                                })

                                if tc.get("error"):
                                    result = tc["error"]
                                    status = "error"
                                else:
                                    try:
                                        result = await self._execute_tool_with_guardrails(tc_id, tc_name, tc_args, auto_apply)
                                        status = "success"
                                    except Exception as e:
                                        result = f"Error executing tool '{tc_name}': {str(e)}"
                                        status = "error"

                                from ..context_helpers import prepare_tool_result_for_history
                                compact_result = prepare_tool_result_for_history(result, tool_name=tc_name)

                                entry = {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": tc_name,
                                    "content": compact_result
                                }
                                if len(str(result)) > len(compact_result):
                                    entry["metadata"] = {
                                        "truncated": True,
                                        "original_chars": len(str(result)),
                                        "retained_chars": len(compact_result)
                                    }
                                tool_results.append(entry)

                                # A8: count wasted turns for diagnostics
                                if any(sig.lower() in result.lower() for sig in _wasted_signals):
                                    if hasattr(self, "wasted_turns"):
                                        self.wasted_turns += 1

                                # Send result back to frontend for chat display
                                await self.send_ws_message({
                                    "type": "tool_result",
                                    "tool_call_id": tc_id,
                                    "name": tc_name,
                                    "status": status,
                                    "result": result
                                })

                    # Append tool outputs to history
                    self.conversation_history.extend(tool_results)

                    # Track tool calls in exec_logger and task_memory
                    if self._exec_logger:
                        for tc in tool_calls_to_run:
                            status = "success"
                            tc_result = next(
                                (r.get("content", "") for r in tool_results if r.get("tool_call_id") == tc["id"]),
                                ""
                            )
                            self._exec_logger.finish_tool_call(result=tc_result, status=status)
                    # Track file writes in task_memory
                    for tc in tool_calls_to_run:
                        if tc["name"] in ("write_file", "edit_file", "patch", "apply_patch"):
                            fp = tc.get("input", {}).get("path") or tc.get("input", {}).get("file_path", "")
                            if fp:
                                self.task_memory.record_write(str(fp))
                    self._agent_tool_call_count += len(tool_calls_to_run)

                    # Continue loop if more turns are needed
                    # (implicitly handled by presence of tool calls)

                if turn >= effective_max_turns:
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": (
                            f"\n\n[WARNING] **Agent reached the maximum limit of {effective_max_turns} turns.** "
                            "To continue, send another message or increase `max_turns` in Settings."
                        )
                    })
                try:
                    from ..project_detector import detect_project_metadata
                    detect_project_metadata(self.workspace_root)
                except Exception as pe:
                    logger.debug(f"Failed auto project detection: {pe}")

                # ── Phase 8+9: Validator + Critic (Agent mode only) ───────────
                if mode == "Agent" and self.task_memory.files_written:
                    try:
                        val_result = self._validator.validate(
                            files_written=self.task_memory.files_written,
                            plan_steps=self.task_memory.to_dict().get("steps"),
                        )
                        if self._exec_logger:
                            self._exec_logger.set_validation(val_result.to_summary())

                        critic_result = self._critic.review(
                            intent=self._current_intent or IntentType.GENERAL,
                            task_memory=self.task_memory,
                            validation_result=val_result,
                            total_turns=turn,
                            response_text=response_text,
                            tool_calls_made=self._agent_tool_call_count,
                        )
                        if self._exec_logger:
                            self._exec_logger.set_critic(critic_result.reason)

                        if not critic_result.complete and turn < effective_max_turns - 1:
                            # Inject critic feedback and run one more turn
                            self.conversation_history.append({
                                "role": "user",
                                "content": (
                                    "[SYSTEM] Critic review found issues that must be fixed:\n"
                                    + critic_result.injected_message
                                )
                            })
                            # Run one extra turn to address critic findings
                            _extra_response = ""
                            async for chunk in self._stream_chat_wrapper(adapter, self._trim_history_for_context(self.conversation_history, system_prompt, tools), tools, system_prompt):
                                if chunk["type"] == "text":
                                    _extra_response += chunk["content"]
                                    await self.send_ws_message({"type": "text_delta", "content": chunk["content"]})
                                elif chunk["type"] == "thinking":
                                    await self.send_ws_message({
                                        "type": "thinking",
                                        "content": chunk.get("thinking", ""),
                                        "signature": chunk.get("signature"),
                                    })
                                elif chunk["type"] == "redacted_thinking":
                                    await self.send_ws_message({
                                        "type": "thinking",
                                        "content": chunk.get("data", "") or "Thinking...",
                                        "signature": "redacted",
                                    })
                            if _extra_response:
                                self.conversation_history.append({"role": "assistant", "content": _extra_response})

                        if not val_result.passed:
                            prompt_block = val_result.to_prompt_block()
                            if prompt_block.strip():
                                await self.send_ws_message({"type": "text_delta", "content": prompt_block})

                    except Exception as ve:
                        logger.warning(f"Validator/Critic error (non-fatal): {ve}")

                # ── Finalize execution logger ─────────────────────────────────
                if self._exec_logger:
                    self._exec_logger.set_cost(getattr(self, "total_cost_usd", 0.0))
                    self._exec_logger.finish("completed")
                    self._exec_logger.emit()

                await self.send_ws_message({
                    "type": "session_done",
                    "total_cost_usd": getattr(self, "total_cost_usd", 0.0),
                    "wasted_turns": getattr(self, "wasted_turns", 0),
                    "task_memory": self.task_memory.to_dict() if mode == "Agent" else None,
                })

        except asyncio.CancelledError:
            # Agent was stopped by the user - send a clean cancellation notice
            await self.send_ws_message({
                "type": "text_delta",
                "content": "\n\n[STOPPED] **Agent stopped** - task was cancelled. You can send a new message to continue."
            })
            await self.send_ws_message({
                "type": "session_done",
                "total_cost_usd": getattr(self, "total_cost_usd", 0.0),
                "wasted_turns": getattr(self, "wasted_turns", 0),
            })
            raise
        except MemoryError:
            logger.exception("Agent crashed: MemoryError")
            await self.send_ws_message({
                "type": "text_delta",
                "content": (
                    "\n\n[OOM] **Agent crashed - Out of Memory**\n\n"
                    "The agent ran out of memory processing your request. "
                    "Try a smaller workspace or close other applications."
                )
            })
            await self.send_ws_message({
                "type": "session_done",
                "total_cost_usd": getattr(self, "total_cost_usd", 0.0),
                "wasted_turns": getattr(self, "wasted_turns", 0),
            })
        except Exception as e:
            # Check if this is a contradiction ValueError
            is_contradiction = False
            if isinstance(e, ValueError):
                contradiction_msg = detect_contradiction(text)
                if contradiction_msg and contradiction_msg in str(e):
                    is_contradiction = True

            if is_contradiction:
                raise e

            import traceback
            tb_lines = traceback.format_exc().splitlines()
            # Show last 6 lines of traceback for context without flooding the chat
            short_tb = "\n".join(tb_lines[-6:])
            error_type = type(e).__name__
            error_msg = str(e) or "(no details)"

            logger.exception(f"Agent crashed [{error_type}]: {error_msg}")

            # Determine a user-friendly hint based on error type
            if "402" in error_msg or "budget" in error_msg.lower() or "credit" in error_msg.lower() or "afford" in error_msg.lower() or error_type == "LLMBudgetExceededError":
                error_title = "Budget / Credits Exceeded"
                hint = (
                    "**[BUDGET EXCEEDED]** Your LLM account has insufficient credits or requested too many `max_tokens`.\n\n"
                    "- Add credits to your provider account (e.g. OpenRouter/OpenAI).\n"
                    "- Or lower the `max_tokens` in Model Settings / Model Configuration."
                )
            elif "403" in error_msg or "forbidden" in error_msg.lower() or "authorization failed" in error_msg.lower() or error_type == "LLMAuthError":
                error_title = "Authentication / Access Denied"
                hint = "**[AUTH ERROR]** Authorization failed (HTTP 403 / 401). Please check your API key and permissions in Settings -> Model Configuration."
            elif "thought_signature" in error_msg.lower() or "400" in error_msg or error_type == "LLMThoughtSignatureError":
                error_title = "Tool / Thought Signature Error"
                hint = "**[MODEL ERROR]** The provider model requires a valid thought signature for tool calls. Please start a new session or switch to another model profile."
            elif "api" in error_msg.lower() or "key" in error_msg.lower() or "auth" in error_msg.lower():
                error_title = "Authentication Error"
                hint = "[HINT] Check your API key in Settings -> Model Configuration."
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower() or error_type == "TimeoutError" or isinstance(e, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
                error_title = "Request Timed Out"
                hint = "[HINT] The model provider timed out. Try again or switch to a faster model."
            elif "rate" in error_msg.lower() or "429" in error_msg:
                error_title = "Rate Limit Reached"
                hint = "[HINT] Rate limit hit. Wait a moment then try again."
            elif "context" in error_msg.lower() or "token" in error_msg.lower() or "413" in error_msg:
                error_title = "Context Window Exceeded"
                hint = "[HINT] Context too large. Start a new session or reduce the number of files."
            elif "NotImplementedError" in error_type:
                error_title = "Feature Not Implemented"
                hint = f"[HINT] Tool '{error_msg}' is not yet supported in this mode."
            elif "connection" in error_msg.lower() or "network" in error_msg.lower():
                error_title = "Network Connection Error"
                hint = "[HINT] Network error. Check your internet connection and try again."
            else:
                error_title = "Agent Error"
                hint = "[HINT] Try rephrasing your request or starting a new session."

            crash_card = (
                f"\n\n> ⚠️ **{error_title}**\n\n"
                f"{hint}\n\n"
                f"**Details:** `{error_msg}`\n\n"
                f"<details><summary>Technical Stack Trace</summary>\n\n"
                f"```\n{short_tb}\n```\n</details>"
            )

            await self.send_ws_message({"type": "text_delta", "content": crash_card})

            # Save the failed request
            self._failed_request = self._last_request_snapshot

            is_timeout = (
                isinstance(e, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException))
                or "timeout" in error_msg.lower()
                or "timed out" in error_msg.lower()
            )
            if is_timeout:
                await self.send_ws_message({
                    "type": "session_failed",
                    "reason": "timeout",
                    "total_cost_usd": getattr(self, "total_cost_usd", 0.0),
                    "wasted_turns": getattr(self, "wasted_turns", 0),
                })
            else:
                await self.send_ws_message({
                    "type": "session_done",
                    "total_cost_usd": getattr(self, "total_cost_usd", 0.0),
                    "wasted_turns": getattr(self, "wasted_turns", 0),
                })
        finally:
            self.is_running = False
            asyncio.create_task(self.save_history_to_db())

    async def handle_simple_ask(self, text: str):
        """
        Handles simple Ask-mode queries directly without multi-agent orchestration overhead.
        """
        adapter = self._get_adapter(is_agent=False)
        system_prompt = self._get_system_prompt("Ask")
        tools = self._get_tools_for_mode("Ask")

        await self.send_ws_message({
            "type": "status",
            "status": "thinking",
            "message": "Thinking..."
        })

        response_text = ""
        try:
            trimmed_history = self._trim_history_for_context(
                self.conversation_history, system_prompt, tools
            )
            async for chunk in self._stream_chat_wrapper(adapter, trimmed_history, tools, system_prompt):
                if chunk["type"] == "text":
                    response_text += chunk["content"]
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": chunk["content"]
                    })
                elif chunk["type"] == "thinking":
                    await self.send_ws_message({
                        "type": "thinking",
                        "content": chunk.get("thinking", ""),
                        "signature": chunk.get("signature"),
                    })
                elif chunk["type"] == "redacted_thinking":
                    await self.send_ws_message({
                        "type": "thinking",
                        "content": chunk.get("data", "") or "Thinking...",
                        "signature": "redacted",
                    })

            if response_text:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_text
                })
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e) or "(no details)"
            short_tb = "\n".join(traceback.format_exc().splitlines()[-6:])

            logger.error(f"Agent crashed in simple ask [{error_type}]: {error_msg}")

            if "api" in error_msg.lower() or "key" in error_msg.lower():
                hint = "[HINT] Check your API key in Settings."
            elif "timeout" in error_msg.lower():
                hint = "[HINT] Request timed out - try again or switch models."
            else:
                hint = "[HINT] Try rephrasing your question."

            crash_card = (
                f"\n\n[CRASH] **Agent Crashed**\n\n"
                f"**Error type:** `{error_type}`\n"
                f"**Details:** {error_msg}\n\n"
                f"{hint}\n\n"
                f"<details><summary>Stack trace</summary>\n\n"
                f"```\n{short_tb}\n```\n</details>"
            )
            await self.send_ws_message({"type": "text_delta", "content": crash_card})
        finally:
            await self.send_ws_message({
                "type": "session_done",
                "total_cost_usd": getattr(self, "total_cost_usd", 0.0)
            })
            asyncio.create_task(self.save_history_to_db())

    async def _execute_tool_with_guardrails(
        self, tc_id: str, name: str, args: dict, auto_apply: bool
    ) -> str:
        """
        Executes a single tool. If the tool is mutative (write/edit) or destructive (terminal commands),
        it prompts the user for confirmation unless auto-apply is true.
        """
        return await dispatch_tool(self, tc_id, name, args, auto_apply)

    async def _run_shell_command(self, command: str) -> str:
        """
        Runs a shell command asynchronously and streams stdout/stderr combined in real time.
        """
        return await run_shell_command(self, command)

    def resolve_confirmation(self, tool_call_id: str, approved: bool, scope: str = "once", edited_command: str = None, hunk_decisions: dict = None):
        """
        Called when the user clicks Accept or Reject in the frontend.
        """
        if tool_call_id in self.pending_confirmations:
            if "action" in self.pending_confirmations[tool_call_id]:
                self.pending_confirmations[tool_call_id]["action"] = scope
                self.pending_confirmations[tool_call_id]["event"].set()
                return
            self.pending_confirmations[tool_call_id]["approved"] = approved
            self.pending_confirmations[tool_call_id]["scope"] = scope
            self.pending_confirmations[tool_call_id]["hunk_decisions"] = hunk_decisions
            if edited_command is not None:
                self.pending_confirmations[tool_call_id]["command"] = edited_command
            self.pending_confirmations[tool_call_id]["event"].set()

    async def _stream_chat_wrapper(self, adapter, messages, tools, system_prompt):
        """
        Wraps adapter.stream_chat to capture usage chunks, calculate costs,
        and enforce cost circuit-breakers:
        - Soft limit (COST_LIMIT_USD, default $5): sends advisory once per session.
        - Hard limit (DEVPILOT_HARD_COST_LIMIT, default $10): immediately terminates.
        """
        from ..config import settings
        from ..adapters.tool_history import clean_tool_history
        cleaned_messages = clean_tool_history(messages)
        soft_limit = float(getattr(settings, "COST_LIMIT_USD", 5.0))
        hard_limit = float(getattr(settings, "DEVPILOT_HARD_COST_LIMIT", 10.0))

        from backend.app.infrastructure.model_gateway import ModelGateway
        async for chunk in ModelGateway.generate_stream(self.profile, cleaned_messages, tools, system_prompt):
            if chunk.get("type") == "usage":
                turn_cost = float(chunk.get("cost_usd", 0.0))
                self.total_cost_usd = self.total_cost_usd + turn_cost

                await self.send_ws_message({
                    "type": "cost_update",
                    "total_cost_usd": round(self.total_cost_usd, 6),
                    "turn_cost_usd": round(turn_cost, 6),
                })

                # ── Cost circuit breakers ─────────────────────────────────
                # Hard limit: immediately stop the agent to prevent runaway costs.
                if self.total_cost_usd >= hard_limit:
                    logger.warning(
                        f"Hard cost limit reached (${self.total_cost_usd:.4f} >= ${hard_limit}). "
                        "Terminating agent session."
                    )
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": (
                            f"\n\n[COST LIMIT] **Session terminated** — total cost "
                            f"${self.total_cost_usd:.4f} exceeded hard limit ${hard_limit:.2f}. "
                            "Increase `DEVPILOT_HARD_COST_LIMIT` in settings to allow higher spend."
                        ),
                    })
                    from backend.app.agent.agent_runtime.runtime import AgentState
                    if hasattr(self, "agent_runtime") and hasattr(self.agent_runtime, "transition_state"):
                        try:
                            self.agent_runtime.transition_state(self, AgentState.BLOCKED)
                        except Exception:
                            pass
                    return  # Stop yielding — caller's loop ends

                # Soft limit: warn once per session so the user is aware.
                if self.total_cost_usd >= soft_limit and not self._cost_advisory_sent:
                    self._cost_advisory_sent = True
                    logger.info(
                        f"Soft cost advisory at ${self.total_cost_usd:.4f} (limit ${soft_limit})"
                    )
                    await self.send_ws_message({
                        "type": "cost_warning",
                        "total_cost_usd": round(self.total_cost_usd, 6),
                        "soft_limit_usd": soft_limit,
                        "hard_limit_usd": hard_limit,
                        "message": (
                            f"Cost advisory: session has spent ${self.total_cost_usd:.4f}. "
                            f"Hard limit is ${hard_limit:.2f}."
                        ),
                    })

            yield chunk

    async def _run_llm_query(self, system_prompt: str, user_content: str, agent_name: str = None) -> str:
        """
        Queries the LLM non-disruptively by accumulating stream_chat chunks.
        """
        from ..adapters.router import ModelRouter
        messages = [{"role": "user", "content": user_content}]
        try:
            router = ModelRouter()
            adapter = router.get_adapter(
                self.profile, is_agent=True, task_type=agent_name
            )
            response_text = ""
            async for chunk in self._stream_chat_wrapper(
                adapter, messages, [], system_prompt
            ):
                if chunk.get("type") == "text":
                    response_text += chunk.get("content", "")
            return response_text
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise



    async def handle_intelligent_recovery(self, proc, original_command: str, framework: str):
        await self.send_ws_message({
            "type": "status",
            "status": "thinking",
            "message": "Terminal Analysis Agent: Diagnosing startup failure..."
        })

        logs_snippet = "".join(proc.logs[-30:])
        prompt = (
            f"The terminal command `{original_command}` failed to start the project. Here are the last few lines of terminal logs:\n"
            f"{logs_snippet}\n\n"
            "Analyze the log output to determine the root cause and propose a fix. If the fix is a command we can run "
            "(e.g. running 'npm install' or 'pip install' or installing a missing package), set 'can_auto_fix' to true and provide the command.\n"
            "Output your response strictly as a JSON object:\n"
            "{\n"
            "  \"root_cause\": \"A clear, user-friendly explanation of why it failed\",\n"
            "  \"fix_suggestion\": \"What needs to be done to fix it\",\n"
            "  \"fix_command\": \"Optional shell command to execute the fix\",\n"
            "  \"can_auto_fix\": true\n"
            "}\n"
            "Respond with ONLY the JSON object, no other text."
        )
        system_prompt = "You are a senior codebase auditor and devops expert. Analyze logs and output JSON diagnostics."

        response = await self._run_llm_query(system_prompt, prompt)

        try:
            clean_res = response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            parsed = json.loads(clean_res.strip())

            root_cause = parsed.get("root_cause", "Unknown error")
            fix_suggestion = parsed.get("fix_suggestion", "Check logs and configure correctly")
            fix_command = parsed.get("fix_command")
            can_auto_fix = parsed.get("can_auto_fix", False)
        except Exception as e:
            logger.error(f"Failed to parse LLM diagnostics response: {str(e)}")
            root_cause = "Unknown startup error."
            fix_suggestion = "Inspect terminal output and dependencies."
            fix_command = None
            can_auto_fix = False

        await self.send_ws_message({
            "type": "text_delta",
            "content": f"### Diagnostic Report\n* **Root Cause:** {root_cause}\n* **Suggestion:** {fix_suggestion}\n\n"
        })

        if can_auto_fix and fix_command:
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Attempting automatic recovery: Running `{fix_command}`...\n"
            })

            is_approved = False
            risk = "mutative"
            reason = "Run Agent automatic fix execution"
            if self.permission_manager:
                is_approved, risk, reason = self.permission_manager.check_permission(fix_command)

            if not is_approved:
                tc_id = f"fix_{uuid.uuid4().hex[:6]}"
                event = asyncio.Event()
                self.pending_confirmations[tc_id] = {
                    "event": event,
                    "approved": False,
                    "scope": "once",
                    "command": fix_command
                }

                await self.send_ws_message({
                    "type": "permission_request",
                    "tool_call_id": tc_id,
                    "tool_name": "run_terminal_command",
                    "command": fix_command,
                    "risk": risk,
                    "reason": reason,
                    "explanation": f"Run Agent wants to run fix command: `{fix_command}`",
                    "args": {"command": fix_command}
                })

                try:
                    await asyncio.wait_for(event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    self.pending_confirmations.pop(tc_id, None)
                    await self.send_ws_message({"type": "text_delta", "content": "*Recovery timed out: no response from client.*\n"})
                    return
                decision = self.pending_confirmations[tc_id]
                del self.pending_confirmations[tc_id]

                if not decision["approved"]:
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": "*Automatic recovery cancelled by user.*\n"
                    })
                    return
                fix_command = decision.get("command", fix_command)

            await self.send_ws_message({
                "type": "status",
                "status": "tool_executing",
                "message": f"Executing fix command: `{fix_command}`..."
            })

            result = await run_shell_command(self, fix_command)
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Fix command finished. Output:\n```\n{result[:500]}...\n```\n"
            })

            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Retrying run command: `{original_command}`\n"
            })

            proc = await global_process_manager.start_process(original_command, self.workspace_root, name=framework, session=self)
            # B6: Store task handle so cancel_all() can cancel it if the user cancels.
            self._monitor_tasks.append(asyncio.create_task(self.monitor_and_stream_events(proc)))

            for _ in range(40):
                await asyncio.sleep(0.25)
                if proc.startup_success_event.is_set():
                    break
                if proc.status in ("stopped", "failed", "crashed"):
                    break

            if proc.status == "running":
                localhost_url = proc.localhost_url or f"http://localhost:{proc.port}"
                network_url = proc.network_url or "N/A"
                port_str = str(proc.port) if proc.port else "N/A"
                content_summary = (
                    "**Application recovered and started successfully!**\n\n"
                    f"Framework: **{framework}**\n"
                    "Status: **Running**\n"
                    f"Local URL: [{localhost_url}]({localhost_url})\n"
                    f"Network URL: {network_url}\n"
                    f"Port: [{port_str}]({localhost_url})\n"
                    f"Process ID: **{proc.pid}**\n"
                )
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": content_summary
                })
            else:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "âŒ Application failed to start after automatic recovery attempt. Please inspect logs.\n"
                })

