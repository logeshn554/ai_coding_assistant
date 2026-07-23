"""AgentSession: conversation loop, tool guardrails, and run-agent flow."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
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

logger = logging.getLogger("devpilot.agent")


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
        self.orchestrator = AgentOrchestrator()
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

    async def enqueue_message(self, text: str, mode: str, auto_apply: bool = False):
        """Queue a user message for sequential processing.

        If the queue is full a 'queue_full' WS event is sent and the message
        is dropped rather than silently overwriting in-flight work.
        """
        if self._message_queue.full():
            await self.send_ws_message({
                "type": "queue_full",
                "content": "⚠️ Request queue is full. Please wait for current tasks to complete before sending more messages.",
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
            try:
                text, mode, auto_apply = await self._message_queue.get()
            except asyncio.CancelledError:
                break

            # Notify frontend that we're starting this item
            await self.send_ws_message({
                "type": "queue_status",
                "queue_depth": self._message_queue.qsize(),
            })

            try:
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

        await self.send_ws_message({
            "type": "queue_status",
            "queue_depth": 0,
        })


    async def load_history_from_db(self):
        try:
            from ..db import async_session, SessionModel
            from sqlalchemy.future import select
            async with async_session() as db:
                stmt = select(SessionModel).where(SessionModel.id == self.session_id)
                res = await db.execute(stmt)
                session_obj = res.scalar()
                if session_obj:
                    raw_history = []
                    for m in session_obj.messages:
                        raw_content = m.content  # May be None or string from DB
                        content = ""
                        tool_calls = None
                        try:
                            if raw_content:
                                parsed = json.loads(raw_content)
                                if isinstance(parsed, dict) and "tool_calls" in parsed:
                                    # New format: {"content": "...", "tool_calls": [...]}
                                    tool_calls = parsed["tool_calls"]
                                    content = str(parsed.get("content") or "")
                                elif isinstance(parsed, str):
                                    content = parsed
                                elif parsed is None:
                                    content = ""
                                else:
                                    # Dict/list without tool_calls: stringify it
                                    content = json.dumps(parsed)
                        except Exception:
                            # Raw string content (not JSON)
                            content = raw_content or ""

                        # Skip orphaned assistant messages: no text and no tool_calls
                        if m.role == "assistant" and not content.strip() and not tool_calls:
                            continue
                        # Skip orphaned tool messages: they reference tool_calls that aren't in history
                        # (will be re-checked after assembling full list)
                        entry: dict = {"role": m.role, "content": content}
                        if tool_calls:
                            entry["tool_calls"] = tool_calls
                        # Restore tool_call_id for tool messages if saved in content
                        if m.role == "tool" and not entry.get("tool_call_id"):
                            entry["tool_call_id"] = "legacy_tool"
                            entry["name"] = entry.get("name", "unknown")
                        raw_history.append(entry)

                    # Final pass: remove orphaned tool messages (no preceding assistant with tool_calls)
                    valid_history = []
                    has_pending_tool_calls = False
                    for entry in raw_history:
                        if entry["role"] == "assistant" and entry.get("tool_calls"):
                            has_pending_tool_calls = True
                        elif entry["role"] == "tool":
                            if not has_pending_tool_calls:
                                continue  # Skip orphaned tool result
                            has_pending_tool_calls = False
                        elif entry["role"] == "user":
                            has_pending_tool_calls = False
                        valid_history.append(entry)

                    self.conversation_history = valid_history
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
                        session_obj = SessionModel(id=self.session_id, title="Default Conversation")
                        db.add(session_obj)
                        await db.flush()

                    msg_stmt = select(MessageModel).where(MessageModel.session_id == self.session_id).order_by(MessageModel.id.asc())
                    msg_res = await db.execute(msg_stmt)
                    existing_msgs = msg_res.scalars().all()

                    n_existing = len(existing_msgs)
                    for i, m in enumerate(self.conversation_history):
                        if i < n_existing:
                            continue

                        role = m.get("role", "user")
                        content = m.get("content", "")
                        tool_calls = m.get("tool_calls")

                        # For assistant messages with tool_calls, serialize the full entry
                        # so that load_history_from_db can reconstruct tool_calls properly
                        if role == "assistant" and tool_calls:
                            db_content = json.dumps({
                                "content": content if content is not None else "",
                                "tool_calls": tool_calls
                            })
                        elif isinstance(content, (dict, list)):
                            db_content = json.dumps(content)
                        else:
                            db_content = content if content is not None else ""

                        msg = MessageModel(
                            session_id=self.session_id,
                            role=role,
                            content=db_content,
                            timestamp=datetime.datetime.utcnow()
                        )
                        db.add(msg)

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
        max_chars: int = 20000  # ~5000 tokens at 4 chars/token
    ) -> list:
        """
        Trims the conversation history so that the total characters (system prompt +
        history + tools JSON) stays within max_chars.  Always keeps the last user
        message and any immediately preceding/following assistant/tool messages so
        that the current turn is never lost.
        Drops from the oldest end of the history.
        """
        tools_chars = len(json.dumps(tools or []))
        system_chars = len(system_prompt or "")
        budget = max(max_chars - system_chars - tools_chars, 2000)

        def msg_chars(m: dict) -> int:
            return len(json.dumps(m))

        total = sum(msg_chars(m) for m in history)
        if total <= budget:
            return history

        # Build a trimmed list by dropping oldest messages first.
        # Never drop if it would leave the history starting with a non-user role.
        trimmed = list(history)
        while trimmed and sum(msg_chars(m) for m in trimmed) > budget:
            # Drop the oldest message, but keep at least 1 user message
            user_count = sum(1 for m in trimmed if m.get("role") == "user")
            if user_count <= 1:
                break  # Keep the last user message no matter what
            trimmed.pop(0)

        # Ensure the list doesn't start with an assistant/tool message (invalid)
        while trimmed and trimmed[0].get("role") in ("assistant", "tool"):
            trimmed.pop(0)

        return trimmed if trimmed else history[-1:]

    def _get_adapter(self, is_agent: bool = False):
        from ..adapters.router import ModelRouter
        from ..state import config_manager
        latest_profile = config_manager.get_active_profile() or self.profile
        router = ModelRouter()
        return router.get_adapter(latest_profile, is_agent=is_agent)

    def _get_tools_for_mode(self, mode: str) -> list:
        read_only_tools = {"list_directory", "read_file", "search_codebase"}
        if mode in ("Ask", "Plan"):
            return [t for t in AVAILABLE_TOOLS if t["name"] in read_only_tools]
        return AVAILABLE_TOOLS

    def _get_system_prompt(self, mode: str) -> str:
        """Build the system prompt for the given operating mode.

        Args:
            mode: Ask, Plan, or Agent.

        Returns:
            Fully rendered master system prompt, including relevant skills.md.
        """
        workspace_context = ""
        from ..workspace_index import WorkspaceIndex
        try:
            ws_indexer = WorkspaceIndex(self.workspace_root)
            context = ws_indexer.get_prompt_context(max_tokens=800)
            if context:
                workspace_context = context
        except Exception as e:
            logger.error(f"Failed to load workspace context: {e}")

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

        prompt = render_system_prompt(
            workspace_root=self.workspace_root,
            mode=mode,
            workspace_context=workspace_context,
            mode_instructions=mode_instructions,
            agent_orchestration_section=agent_orchestration_section,
        )
        if skills_section:
            prompt = prompt.rstrip() + "\n\n" + skills_section
        return prompt

    async def handle_user_message(self, text: str, mode: str, auto_apply: bool = False):
        """
        Runs the agent loop for a user query.
        """
        self.auto_apply = auto_apply
        if self.is_running:
            await self.send_ws_message({
                "type": "text_delta",
                "content": "\n[Error: Agent is already running another task.]\n"
            })
            await self.send_ws_message({"type": "session_done"})
            return

        # Check for Run Agent activation (precise patterns only)
        RUN_PATTERNS = [
            r'\b(run|start|launch|execute|serve)\s+(the\s+)?(project|app|application|server|frontend|backend|api)\b',
            r'\b(build\s+and\s+run|start\s+server|run\s+project|open\s+application|preview\s+(the\s+)?app)\b',
            r'\bstart\s+(the\s+)?(dev\s+)?server\b',
            r'\bnpm\s+(run|start)\b',
            r'\buvicorn\b',
            r'\bpython\s+-m\b',
        ]
        is_run_command = any(re.search(p, text.lower()) for p in RUN_PATTERNS)

        if is_run_command:
            self.is_running = True
            try:
                self.conversation_history.append({"role": "user", "content": text})
                await self.run_agent_flow(text)
            except Exception as e:
                logger.exception(f"Run Agent execution failed: {str(e)}")
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"\n\n[Run Agent Error: {str(e)}]\n"
                })
            finally:
                self.is_running = False
                await self.save_history_to_db()
                await self.send_ws_message({"type": "session_done"})
                await self.broadcast_processes_state()
            return

        self.is_running = True
        try:
            # Append user request to history
            self.conversation_history.append({"role": "user", "content": text})

            # Auto-route mode selection if set to 'Auto'
            if mode == "Auto":
                # ── Fast-path router: classify trivial inputs without an LLM call ──
                _t = text.strip().lower().rstrip("!?.,:;")

                _GREETINGS = {
                    "hi", "hello", "hey", "yo", "sup", "hiya", "howdy",
                    "thanks", "thank you", "ty", "thx", "ok", "okay",
                    "yes", "no", "sure", "cool", "got it", "alright",
                    "great", "perfect", "good", "nice", "awesome"
                }
                if _t in _GREETINGS:
                    mode = "Ask"
                elif len(text.strip()) < 15 and not any(
                    kw in _t for kw in ["create", "write", "fix", "run", "build", "add", "edit", "delete", "install"]
                ):
                    mode = "Ask"
                elif re.search(
                    r'\b(create|write|build|fix|run|start|launch|install|refactor|edit|delete|add|generate|deploy|implement|test)\b',
                    _t
                ):
                    mode = "Agent"
                else:
                    system_prompt = (
                        "You are a query classifier for a coding IDE. "
                        "Read the user's message and return EXACTLY one word: Ask, Plan, or Agent.\n\n"
                        "RULES — read carefully:\n"
                        "  Ask   → Greetings, questions, explanations, definitions, help requests, code review "
                        "without changes, 'what is X', 'how does X work', 'explain Y', 'hi', 'hello', 'thanks'.\n"
                        "  Plan  → User explicitly wants a plan, outline, roadmap, or architecture design "
                        "WITHOUT implementation. Keywords: 'plan', 'design', 'outline', 'propose', 'think through'.\n"
                        "  Agent → User wants ACTIONS: create files, edit code, fix bugs, run commands, "
                        "install packages, write tests, refactor, build, deploy, start server.\n\n"
                        "CRITICAL RULES:\n"
                        "  - A greeting like 'hi', 'hello', 'hey', 'thanks' is ALWAYS Ask.\n"
                        "  - A question starting with 'what', 'why', 'how', 'explain', 'can you tell me' is ALWAYS Ask.\n"
                        "  - 'Write me a function' IS Agent (creates code).\n"
                        "  - 'Explain this function' IS Ask (no changes).\n"
                        "  - When uncertain between Ask and Plan, choose Ask.\n"
                        "  - When uncertain between Plan and Agent, choose Plan.\n\n"
                        "EXAMPLES:\n"
                        "  hi                              → Ask\n"
                        "  hello, how are you              → Ask\n"
                        "  what is a decorator in python   → Ask\n"
                        "  explain how JWT works           → Ask\n"
                        "  review this code                → Ask\n"
                        "  plan a REST API for my app      → Plan\n"
                        "  design the database schema      → Plan\n"
                        "  create a login page             → Agent\n"
                        "  fix the bug in auth.py          → Agent\n"
                        "  run the tests                   → Agent\n"
                        "  add a dark mode toggle          → Agent\n"
                        "  refactor the user service       → Agent\n\n"
                        "Reply with ONLY one of these three words. No punctuation. No explanation."
                    )
                    try:
                        response = await self._run_llm_query(system_prompt, text, agent_name="Orchestrator Agent")
                        classified = response.strip().strip("'\"").strip()
                        if classified in ["Ask", "Plan", "Agent"]:
                            mode = classified
                        else:
                            if "ask" in classified.lower():
                                mode = "Ask"
                            elif "plan" in classified.lower():
                                mode = "Plan"
                            elif "agent" in classified.lower():
                                mode = "Agent"
                            else:
                                mode = "Ask"  # Safe default — never assume expensive work is needed
                    except Exception as e:
                        logger.error(f"Failed to auto-classify query using LLM: {str(e)}")
                        mode = "Ask"
                logger.info(f"Auto-routed query '{text}' using LLM to mode: '{mode}'")

            # Trigger multi-agent collaboration flow
            if mode == "Agent":
                try:
                    max_steps = self.profile.get("max_orchestrator_steps") or self.profile.get("max_steps") or 30
                    self.orchestrator.max_steps = int(max_steps)
                    await self.orchestrator.run_task(text, self)
                except Exception as e:
                    logger.error(f"Orchestrator run failed: {str(e)}")
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": f"\n[Orchestrator Error: {str(e)}]\n"
                    })
                await self.send_ws_message({"type": "session_done"})
                return

            adapter = self._get_adapter()
            system_prompt = self._get_system_prompt(mode)
            tools = self._get_tools_for_mode(mode)

            turn = 0
            while turn < self.max_turns:
                turn += 1

                # Send status update
                await self.send_ws_message({
                    "type": "status",
                    "status": "thinking",
                    "message": f"Thinking (Turn {turn}/{self.max_turns})..."
                })

                response_text = ""
                tool_calls_to_run = []

                # 1. Stream the model's text response and collect tool calls
                try:
                    # Trim history to fit within token budget before each API call
                    trimmed_history = self._trim_history_for_context(
                        self.conversation_history, system_prompt, tools
                    )
                    async for chunk in adapter.stream_chat(trimmed_history, tools, system_prompt):
                        if chunk["type"] == "text":
                            response_text += chunk["content"]
                            await self.send_ws_message({
                                "type": "text_delta",
                                "content": chunk["content"]
                            })
                        elif chunk["type"] == "tool_call":
                            tool_calls_to_run.append(chunk)
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
                            async for chunk in adapter.stream_chat(trimmed_history, tools, system_prompt):
                                if chunk["type"] == "text":
                                    response_text += chunk["content"]
                                    await self.send_ws_message({
                                        "type": "text_delta",
                                        "content": chunk["content"]
                                    })
                                elif chunk["type"] == "tool_call":
                                    tool_calls_to_run.append(chunk)
                                elif chunk["type"] == "done":
                                    stop_reason = chunk["stop_reason"]
                        except Exception as retry_err:
                            raise retry_err
                    else:
                        raise e

                # 2. Append assistant response to history
                assistant_msg = {
                    "role": "assistant",
                    "content": response_text
                }
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
                for tc in tool_calls_to_run:
                    tc_id = tc["id"]
                    tc_name = tc["name"]
                    tc_args = tc["input"]

                    await self.send_ws_message({
                        "type": "status",
                        "status": "tool_executing",
                        "message": f"Preparing tool '{tc_name}'...",
                        "tool_call": {"id": tc_id, "name": tc_name, "args": tc_args}
                    })

                    try:
                        result = await self._execute_tool_with_guardrails(tc_id, tc_name, tc_args, auto_apply)
                        status = "success"
                    except Exception as e:
                        result = f"Error executing tool '{tc_name}': {str(e)}"
                        status = "error"

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": result
                    })

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

                # Continue loop if more turns are needed
                # (implicitly handled by presence of tool calls)

            if turn >= self.max_turns:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "\n\n[Warning: Agent reached the maximum limit of 25 turns.]"
                })
            await self.send_ws_message({"type": "session_done"})

        except asyncio.CancelledError:
            await self.send_ws_message({"type": "session_done"})
            raise
        except Exception as e:
            logger.exception(f"Error in handle_user_message agent loop: {str(e)}")
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"\n\n[Error: {str(e)}]\n"
            })
            await self.send_ws_message({"type": "session_done"})
        finally:
            self.is_running = False
            await self.save_history_to_db()

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
            async for chunk in adapter.stream_chat(trimmed_history, tools, system_prompt):
                if chunk["type"] == "text":
                    response_text += chunk["content"]
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": chunk["content"]
                    })

            if response_text:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response_text
                })
        except Exception as e:
            logger.error(f"Error handling simple ask: {str(e)}")
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"\n[Error: {str(e)}]\n"
            })
        finally:
            await self.send_ws_message({"type": "session_done"})
            await self.save_history_to_db()

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

    async def _run_llm_query(self, system_prompt: str, user_content: str, agent_name: str = None) -> str:
        """
        Queries the LLM non-disruptively by accumulating stream_chat chunks.
        Uses ModelRouter to support automatic local model fallbacks on connection/API failure.
        """
        from ..adapters.router import ModelRouter
        messages = [{"role": "user", "content": user_content}]
        try:
            router = ModelRouter()
            response_text = await router.completion(self.profile, messages, system_prompt, is_agent=True, task_type=agent_name)
            return response_text
        except Exception as e:
            logger.error(f"Error querying background LLM (including fallbacks): {str(e)}")
            raise e

    async def broadcast_processes_state(self):
        from ..processes import global_process_manager
        procs = global_process_manager.get_all_processes()
        serialized = []
        for p in procs:
            serialized.append({
                "id": p.id,
                "name": p.name,
                "command": p.command,
                "status": p.status,
                "port": p.port,
                "localhost_url": p.localhost_url,
                "network_url": p.network_url,
                "pid": p.pid
            })
        await self.send_ws_message({
            "type": "processes_update",
            "processes": serialized
        })

    async def monitor_and_stream_events(self, proc):
        await self.broadcast_processes_state()
        last_index = 0
        reported_events = set()
        while proc.status in ("starting", "running"):
            if last_index < len(proc.logs):
                new_lines = proc.logs[last_index:]
                last_index = len(proc.logs)
                for line in new_lines:
                    await self.send_ws_message({
                        "type": "terminal_stream",
                        "content": line
                    })
                    line_lower = line.lower()
                    event_msg = None
                    if "hmr update" in line_lower or "hot update" in line_lower:
                        event_msg = "✓ Hot Reload completed"
                    elif "compiled successfully" in line_lower:
                        event_msg = "✓ Build completed successfully"
                    elif "database connected" in line_lower or "db connected" in line_lower or "connected to database" in line_lower:
                        event_msg = "✓ Connected to database"
                    elif "api ready" in line_lower or "api server ready" in line_lower:
                        event_msg = "✓ API server ready"
                    elif "rebuilding" in line_lower or "rebuilt" in line_lower:
                        event_msg = "✓ Server rebuild complete"

                    if event_msg and event_msg not in reported_events:
                        await self.send_ws_message({
                            "type": "text_delta",
                            "content": f"\n{event_msg}\n"
                        })
                        reported_events.add(event_msg)
            await asyncio.sleep(0.1)
        await self.broadcast_processes_state()

    async def run_agent_flow(self, user_text: str):
        await self.send_ws_message({
            "type": "status",
            "status": "thinking",
            "message": "Run Agent: Detecting project type..."
        })

        files_list = []
        try:
            items = await async_list_workspace_dir(self.workspace_root, "")
            for it in items:
                files_list.append(it["name"])
                if it.get("is_dir", it.get("isDir", False)) and it["name"] not in (".git", "node_modules", "venv", "__pycache__", ".devpilot"):
                    try:
                        sub_items = await async_list_workspace_dir(self.workspace_root, it["name"])
                        for s_it in sub_items[:15]:
                            files_list.append(f"{it['name']}/{s_it['name']}")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error listing workspace files: {str(e)}")

        pkg_scripts_summary = []
        for pf in files_list:
            if pf.endswith("package.json"):
                try:
                    full_p = safe_path(self.workspace_root, pf)
                    if os.path.exists(full_p):
                        with open(full_p, "r", encoding="utf-8") as f:
                            pdata = json.load(f)
                            pkg_scripts_summary.append(f"File '{pf}' scripts: {json.dumps(pdata.get('scripts', {}))}")
                except Exception:
                    pass

        pkg_details_str = "\n".join(pkg_scripts_summary) if pkg_scripts_summary else "No package.json scripts detected."

        prompt = (
            f"The user wants to run/start the project. User request: '{user_text}'\n"
            f"Workspace files:\n{json.dumps(files_list, indent=2)}\n\n"
            f"Detected Package Scripts:\n{pkg_details_str}\n\n"
            "Analyze the workspace files, package scripts, and the user request to determine:\n"
            "1. The project/service type or framework (e.g. 'React (Vite)', 'FastAPI', 'Python Flask', etc.).\n"
            "2. The exact terminal command to run, start, or serve the requested service/project.\n"
            "Ensure the command is correct for this project structure. If a package.json is in a subdirectory (like 'frontend'), include the prefix (e.g. 'npm run dev --prefix frontend') or correct relative command.\n"
            "Only suggest 'npm run dev' or 'npm start' if that script actually exists in the package.json scripts!\n\n"
            "Output your response strictly as a JSON object with two fields:\n"
            "- 'framework': a string indicating the framework/language/service name (e.g. 'React (Vite)', 'FastAPI', 'Flask', 'Django', etc.)\n"
            "- 'command': the exact command to run/start/serve the application (e.g. 'npm run dev', 'uvicorn main:app --reload', etc.)\n"
            "Respond with ONLY the JSON object, no other text."
        )
        system_prompt = "You are a master developer assistant. Analyze the project structure and output the correct run command in JSON format."

        response = await self._run_llm_query(system_prompt, prompt)

        try:
            clean_res = response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            parsed = json.loads(clean_res.strip())
            framework = parsed.get("framework") or "Unknown Framework"
            command = parsed.get("command")
            if not command or not isinstance(command, str) or not command.strip():
                raise ValueError("Command field is missing, empty, or not a string in LLM response.")
        except Exception as e:
            logger.error(f"Failed to parse LLM run command JSON: {str(e)}")
            framework = "Unknown"
            # Smart fallback based on package.json scripts
            command = None
            if pkg_scripts_summary:
                for line in pkg_scripts_summary:
                    if '"dev"' in line:
                        prefix = " --prefix " + line.split("File '")[1].split("/package.json")[0] if "/package.json" in line else ""
                        command = f"npm run dev{prefix}"
                        break
                    elif '"start"' in line:
                        prefix = " --prefix " + line.split("File '")[1].split("/package.json")[0] if "/package.json" in line else ""
                        command = f"npm start{prefix}"
                        break
            if not command:
                if "main.py" in files_list or any(f.endswith("/main.py") for f in files_list):
                    command = "python main.py"
                else:
                    command = "python -m http.server 8000"

        # Auto-adjust npm command to include --prefix if root package.json does not exist
        if command and command.startswith("npm ") and "--prefix" not in command:
            root_pkg = safe_path(self.workspace_root, "package.json")
            if not os.path.exists(root_pkg):
                for pf in files_list:
                    if pf.endswith("package.json") and "/" in pf:
                        sub_folder = pf.rsplit("/package.json", 1)[0]
                        command = f"{command} --prefix {sub_folder}"
                        logger.info(f"Auto-adjusted npm command to include prefix: '{command}'")
                        break

        await self.send_ws_message({
            "type": "text_delta",
            "content": f"**Detected project type:** {framework}\n**Suggested command:** `{command}`\n\n"
        })

        is_approved = False
        risk = "mutative"
        reason = "Run Agent execution"
        if self.permission_manager:
            is_approved, risk, reason = self.permission_manager.check_permission(command)

        if not is_approved:
            tc_id = f"run_{uuid.uuid4().hex[:6]}"
            event = asyncio.Event()
            self.pending_confirmations[tc_id] = {
                "event": event,
                "approved": False,
                "scope": "once",
                "command": command
            }

            await self.send_ws_message({
                "type": "permission_request",
                "tool_call_id": tc_id,
                "tool_name": "run_terminal_command",
                "command": command,
                "risk": risk,
                "reason": reason,
                "explanation": f"The Run Agent wants to run the project using command: `{command}`",
                "args": {"command": command}
            })

            try:
                await asyncio.wait_for(event.wait(), timeout=300)
            except asyncio.TimeoutError:
                self.pending_confirmations.pop(tc_id, None)
                await self.send_ws_message({"type": "text_delta", "content": "*Execution timed out: no response from client.*\n"})
                return
            decision = self.pending_confirmations[tc_id]
            del self.pending_confirmations[tc_id]

            if not decision["approved"]:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "*Execution cancelled by the user.*\n"
                })
                return
            command = decision.get("command", command)

        await self.send_ws_message({
            "type": "status",
            "status": "tool_executing",
            "message": f"Starting project with `{command}`..."
        })

        proc = await global_process_manager.start_process(command, self.workspace_root, name=framework)
        asyncio.create_task(self.monitor_and_stream_events(proc))

        for _ in range(40):
            await asyncio.sleep(0.25)
            if proc.startup_success_event.is_set():
                break
            if proc.status in ("stopped", "failed", "crashed"):
                break

        if proc.port_conflict:
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"⚠️ Port conflict detected: Port {proc.port} is already in use.\n"
            })

            conflict_pid, conflict_name = get_process_using_port(proc.port)
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Process `{conflict_name}` (PID: {conflict_pid}) is using port {proc.port}.\n"
            })

            tc_id = f"port_{uuid.uuid4().hex[:6]}"
            event = asyncio.Event()
            self.pending_confirmations[tc_id] = {
                "event": event,
                "action": None
            }

            await self.send_ws_message({
                "type": "port_conflict_request",
                "tool_call_id": tc_id,
                "port": proc.port,
                "pid": conflict_pid,
                "process_name": conflict_name
            })

            try:
                await asyncio.wait_for(event.wait(), timeout=300)
            except asyncio.TimeoutError:
                self.pending_confirmations.pop(tc_id, None)
                await self.send_ws_message({"type": "text_delta", "content": "*Port conflict resolution timed out.*\n"})
                await global_process_manager.stop_process(proc.id)
                return
            action = self.pending_confirmations[tc_id].get("action")
            del self.pending_confirmations[tc_id]

            if action == "stop":
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Stopping conflicting process `{conflict_name}` (PID: {conflict_pid})...\n"
                })
                kill_process_by_pid(conflict_pid)
                await global_process_manager.stop_process(proc.id)
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Retrying run command: `{command}`\n"
                })
                proc = await global_process_manager.start_process(command, self.workspace_root, name=framework)
                asyncio.create_task(self.monitor_and_stream_events(proc))
                for _ in range(40):
                    await asyncio.sleep(0.25)
                    if proc.startup_success_event.is_set():
                        break
                    if proc.status in ("stopped", "failed", "crashed"):
                        break
            elif action == "next_port":
                next_port = proc.port + 1
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Determining run command for next available port: {next_port}...\n"
                })
                rewrite_prompt = (
                    f"The run command `{command}` failed because port {proc.port} is in use.\n"
                    f"Please modify the command so it runs on port {next_port}.\n"
                    "Respond with ONLY the modified command string, e.g. 'PORT=5174 npm run dev' or 'uvicorn main:app --port 8001'."
                )
                new_command = await self._run_llm_query("You are a devops engineer helper.", rewrite_prompt)
                new_command = new_command.strip().strip("`").strip()

                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Retrying with command: `{new_command}`\n"
                })
                await global_process_manager.stop_process(proc.id)
                proc = await global_process_manager.start_process(new_command, self.workspace_root, name=framework)
                asyncio.create_task(self.monitor_and_stream_events(proc))
                for _ in range(40):
                    await asyncio.sleep(0.25)
                    if proc.startup_success_event.is_set():
                        break
                    if proc.status in ("stopped", "failed", "crashed"):
                        break
            else:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "Startup cancelled by the user.\n"
                })
                await global_process_manager.stop_process(proc.id)
                return

        if proc.status == "running":
            localhost_url = proc.localhost_url or f"http://localhost:{proc.port}"
            network_url = proc.network_url or "N/A"
            port_str = str(proc.port) if proc.port else "N/A"

            content_summary = (
                "**Application started successfully.**\n\n"
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
                "content": "❌ Application failed to start.\n"
            })
            await self.handle_intelligent_recovery(proc, command, framework)

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

            result = await self._run_shell_command(fix_command)
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Fix command finished. Output:\n```\n{result[:500]}...\n```\n"
            })

            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Retrying run command: `{original_command}`\n"
            })

            await global_process_manager.stop_process(proc.id)
            proc = await global_process_manager.start_process(original_command, self.workspace_root, name=framework)
            asyncio.create_task(self.monitor_and_stream_events(proc))

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
                    "content": "❌ Application failed to start after automatic recovery attempt. Please inspect logs.\n"
                })
