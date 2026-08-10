import os
import json
import uuid
import secrets
import datetime
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from ..state import workspace_state, config_manager, get_permission_manager, SESSION_TOKEN, logger
from ..db import async_session, SessionModel, MessageModel, get_fallback_session_id
from fastapi import Request
from ..session.agent_session import AgentSession

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Live Chat Logger
# Writes every event (user messages, thinking, tool calls, AI responses)
# to  <workspace>/.devpilot/chat_logs.md  in real time.
# ─────────────────────────────────────────────────────────────────────────────

class ChatLogger:
    """Appends structured chat events to the active workspace's chat_logs.md dynamically."""

    def __init__(self, session_id: str):
        self._session_id = session_id
        self._in_ai_block = False
        self._has_logged_session_start = False
        # Create a unique, date-stamped filename per chat session
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_filename = f"chat_log_{date_str}_{session_id}.md"
        self._write_buffer = ""
        self._write_count = 0

    def _ts(self) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _ensure_session_start(self):
        if not self._has_logged_session_start:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._raw_write(f"\n## 📋 Session `{self._session_id}` — {ts}\n\n")
            self._has_logged_session_start = True

    def _close_ai_block_if_needed(self):
        if self._in_ai_block:
            self._raw_write("\n\n---\n\n")
            self._in_ai_block = False
            self.flush()

    def flush(self):
        if not self._write_buffer:
            return
        text = self._write_buffer
        self._write_buffer = ""
        self._write_count = 0

        root = workspace_state.root
        if not root or not os.path.isdir(root):
            return
        try:
            log_dir = os.path.join(root, ".devpilot")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, self._log_filename)
            
            if not os.path.exists(log_path):
                header = (
                    f"# DevPilot Chat Session Log\n"
                    f"> Session ID: `{self._session_id}`\n"
                    f"> Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"---\n\n"
                )
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(header)
            
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            logger.debug(f"ChatLogger write error: {e}")

    def _raw_write(self, text: str):
        self._write_buffer += text
        self._write_count += 1
        if self._write_count >= 20 or len(self._write_buffer) >= 2048:
            self.flush()

    def log_user(self, text: str):
        self._ensure_session_start()
        self._close_ai_block_if_needed()
        self._raw_write(
            f"### 👤 User  `{self._ts()}`\n"
            f"```\n{text.strip()}\n```\n\n"
        )
        self.flush()

    def log_thinking(self, content: str):
        self._ensure_session_start()
        self._close_ai_block_if_needed()
        snippet = content.strip()[:400]
        if len(content) > 400:
            snippet += "…"
        self._raw_write(
            f"### 💭 Thinking  `{self._ts()}`\n"
            f"> {snippet}\n\n"
        )
        self.flush()

    def log_tool_call(self, tool_name: str, tool_id: str, args: dict):
        self._ensure_session_start()
        self._close_ai_block_if_needed()
        args_str = json.dumps(args, ensure_ascii=False)[:300]
        self._raw_write(
            f"### 🛠️ Tool Called — `{tool_name}`  `{self._ts()}`\n"
            f"- **ID**: `{tool_id}`\n"
            f"- **Args**: `{args_str}`\n\n"
        )
        self.flush()

    def log_tool_result(self, tool_name: str, tool_id: str, result: str, status: str):
        self._ensure_session_start()
        self._close_ai_block_if_needed()
        icon = "✅" if status == "success" else "❌"
        snippet = str(result).strip()[:500]
        if len(str(result)) > 500:
            snippet += "…"
        self._raw_write(
            f"### 📥 Tool Result — `{tool_name}`  `{self._ts()}`  {icon}\n"
            f"- **ID**: `{tool_id}`\n"
            f"- **Status**: `{status}`\n"
            f"```\n{snippet}\n```\n\n"
        )
        self.flush()

    def log_ai_chunk(self, chunk: str):
        self._ensure_session_start()
        if not self._in_ai_block:
            self._raw_write(f"### 🤖 AI Response  `{self._ts()}`\n")
            self._in_ai_block = True
        self._raw_write(chunk)

    def log_status(self, message: str):
        self._ensure_session_start()
        self._close_ai_block_if_needed()
        self._raw_write(f"**⚙️ Status** `{self._ts()}`: {message}\n\n")
        self.flush()


class ChatHistoryRequest(BaseModel):
    messages: list

class ChatSessionCreateRequest(BaseModel):
    title: str

class ChatSessionRenameRequest(BaseModel):
    title: str

class ChatSessionSaveRequest(BaseModel):
    messages: list

class TokenizeRequest(BaseModel):
    messages: list
    open_files: list[str]

async def resolve_session_id(request: Request = None, session_id: Optional[str] = None) -> str:
    if session_id:
        return session_id
    if request:
        s_id = request.query_params.get("session_id")
        if s_id:
            return s_id
        s_id = request.headers.get("X-Session-ID")
        if s_id:
            return s_id
    return await get_fallback_session_id(workspace_state.root)

@router.post("/api/chat/tokenize")
async def tokenize_chat_context(req: TokenizeRequest):
    try:
        total_chars = 0
        for msg in req.messages:
            content = msg.get("content") or ""
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            total_chars += len(str(content))
            
        file_contents = []
        for rel_path in req.open_files:
            if not workspace_state.root:
                continue
            from ..files import safe_path
            try:
                abs_path = safe_path(rel_path, workspace_state.root)
                if os.path.isfile(abs_path):
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        fc = f.read()
                        total_chars += len(fc)
                        file_contents.append(fc)
            except Exception:
                pass

        # Local approximation: total_chars / 3.5 is accurate within ~10% and instant.
        tokens = max(120, int(total_chars / 3.5))
        # Add 15% safety buffer so the UI warns before actual context overflow
        tokens = int(tokens * 1.15)
        return {"tokens": tokens}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chat/history")
async def get_chat_history(request: Request, session_id: Optional[str] = None):
    active_id = await resolve_session_id(request, session_id)
    async with async_session() as db:
        stmt = select(SessionModel).where(SessionModel.id == active_id)
        res = await db.execute(stmt)
        session = res.scalar()
        if not session:
            return {"messages": []}
        
        messages_list = []
        for m in session.messages:
            content = m.content
            try:
                content = json.loads(m.content)
            except Exception:
                pass
            messages_list.append({
                "role": m.role,
                "content": content,
                "timestamp": int(m.timestamp.timestamp())
            })
        return {"messages": messages_list}

@router.post("/api/chat/history")
async def save_chat_history(req: ChatHistoryRequest, request: Request, session_id: Optional[str] = None):
    active_id = await resolve_session_id(request, session_id)
    try:
        async with async_session() as db:
            async with db.begin():
                stmt = select(SessionModel).where(SessionModel.id == active_id)
                res = await db.execute(stmt)
                session = res.scalar()
                if not session:
                    session = SessionModel(id=active_id, title="Default Conversation")
                    db.add(session)
                    await db.flush()
                    
                msg_stmt = select(MessageModel).where(MessageModel.session_id == active_id).order_by(MessageModel.id.asc())
                msg_res = await db.execute(msg_stmt)
                existing_msgs = msg_res.scalars().all()
                
                n_existing = len(existing_msgs)
                
                for i, m in enumerate(req.messages):
                    if i < n_existing:
                        continue
                        
                    role = m.get("role", "user")
                    content = m.get("content", "")
                    if isinstance(content, (dict, list)):
                        content = json.dumps(content)
                        
                    m_ts = m.get("timestamp")
                    if m_ts:
                        dt = datetime.datetime.utcfromtimestamp(m_ts)
                    else:
                        dt = datetime.datetime.utcnow()
                        
                    msg = MessageModel(
                        session_id=active_id,
                        role=role,
                        content=content,
                        timestamp=dt
                    )
                    db.add(msg)
                    
                session.updated_at = datetime.datetime.utcnow()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chat/sessions")
async def get_chat_sessions(request: Request):
    from ..db import first_user_preview
    async with async_session() as db:
        stmt = select(SessionModel).order_by(SessionModel.updated_at.desc())
        res = await db.execute(stmt)
        sessions = res.scalars().all()

        root = (workspace_state.root or "").strip()
        if root:
            scoped = [s for s in sessions if (s.workspace_root or "") == root]
            if scoped:
                sessions = scoped

        sessions_list = []
        for s in sessions:
            payloads = []
            for m in (s.messages or []):
                content = m.content
                try:
                    content = json.loads(m.content)
                except Exception:
                    pass
                payloads.append({"role": m.role, "content": content})
            sessions_list.append({
                "id": s.id,
                "title": s.title,
                "workspace_root": s.workspace_root or "",
                "mode": s.mode or "Ask",
                "created_at": int(s.created_at.timestamp()),
                "updated_at": int(s.updated_at.timestamp()),
                "message_count": len(s.messages or []),
                "first_user_message": first_user_preview(payloads, 60),
            })

        active_id = await resolve_session_id(request)
        return {
            "sessions": sessions_list,
            "active_session_id": active_id
        }

@router.post("/api/chat/sessions")
async def create_chat_session(req: ChatSessionCreateRequest):
    new_id = f"session_{uuid.uuid4().hex[:8]}"
    try:
        async with async_session() as db:
            new_session = SessionModel(
                id=new_id,
                title=req.title.strip() or "New Chat",
                workspace_root=workspace_state.root or "",
                mode="Ask",
                messages_json="[]",
            )
            db.add(new_session)
            await db.commit()

            return {
                "success": True,
                "session": {
                    "id": new_id,
                    "title": new_session.title,
                    "workspace_root": new_session.workspace_root or "",
                    "mode": new_session.mode or "Ask",
                    "created_at": int(new_session.created_at.timestamp()),
                    "updated_at": int(new_session.updated_at.timestamp()),
                    "message_count": 0,
                    "first_user_message": "",
                    "messages": []
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chat/sessions/{session_id}")
async def get_chat_session_details(session_id: str):
    async with async_session() as db:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        messages_list = []
        for m in session.messages:
            content = m.content
            try:
                content = json.loads(m.content)
            except Exception:
                pass
            
            msg_entry = {
                "role": m.role,
                "timestamp": int(m.timestamp.timestamp())
            }
            if isinstance(content, dict) and ("content" in content or "tool_calls" in content or "thinking_blocks" in content):
                msg_entry["content"] = content.get("content") or ""
                for k, v in content.items():
                    if k != "content":
                        msg_entry[k] = v
            else:
                msg_entry["content"] = content
                
            messages_list.append(msg_entry)
            
        return {
            "session": {
                "id": session.id,
                "title": session.title,
                "created_at": int(session.created_at.timestamp()),
                "updated_at": int(session.updated_at.timestamp()),
                "messages": messages_list
            }
        }

@router.put("/api/chat/sessions/{session_id}")
async def rename_chat_session(session_id: str, req: ChatSessionRenameRequest):
    try:
        async with async_session() as db:
            stmt = select(SessionModel).where(SessionModel.id == session_id)
            res = await db.execute(stmt)
            session = res.scalar()
            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
            
            session.title = req.title.strip()
            session.updated_at = datetime.datetime.utcnow()
            await db.commit()
            
            return {
                "success": True,
                "session": {
                    "id": session.id,
                    "title": session.title,
                    "created_at": int(session.created_at.timestamp()),
                    "updated_at": int(session.updated_at.timestamp())
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str, request: Request):
    try:
        async with async_session() as db:
            stmt = select(SessionModel).where(SessionModel.id == session_id)
            res = await db.execute(stmt)
            session = res.scalar()
            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
            
            await db.delete(session)
            await db.flush()
            await db.commit()
            
            # Evict from memory mapping to avoid leaks
            workspace_state.evict_session(session_id)
            
            # Check if database is empty now for this workspace
            workspace_root_val = (workspace_state.root or "").strip()
            res_remaining = await db.execute(
                select(SessionModel)
                .where(SessionModel.workspace_root == workspace_root_val)
                .order_by(SessionModel.updated_at.desc())
            )
            latest = res_remaining.scalars().first()
            if not latest:
                # To prevent unique/primary key conflicts across workspaces:
                stmt_check = select(SessionModel).where(SessionModel.id == "default-session")
                res_check = await db.execute(stmt_check)
                exist_default = res_check.scalar()
                
                new_default_id = "default-session" if not exist_default else f"default-session-{uuid.uuid4().hex[:8]}"
                default_session = SessionModel(
                    id=new_default_id,
                    title="Default Conversation",
                    workspace_root=workspace_root_val
                )
                db.add(default_session)
                await db.commit()
                    
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/chat/sessions")
async def clear_all_sessions():
    try:
        workspace_root_val = (workspace_state.root or "").strip()
        if not workspace_root_val:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        async with async_session() as db:
            await db.execute(delete(SessionModel).where(SessionModel.workspace_root == workspace_root_val))
            await db.flush()
            
            stmt_check = select(SessionModel).where(SessionModel.id == "default-session")
            res_check = await db.execute(stmt_check)
            exist_default = res_check.scalar()
            
            default_id = "default-session" if not exist_default else f"default-session-{uuid.uuid4().hex[:8]}"
            default_session = SessionModel(
                id=default_id,
                title="Default Conversation",
                workspace_root=workspace_root_val
            )
            db.add(default_session)
            await db.commit()

        # Evict all memory sessions belonging to this workspace root to prevent leaks
        roots_to_evict = [sid for sid, path in list(workspace_state._session_roots.items()) if path == workspace_root_val]
        for sid in roots_to_evict:
            workspace_state.evict_session(sid)

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from ..state import limiter

@router.websocket("/ws/chat")
async def websocket_chat(
    request: WebSocket,
    token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    await request.accept()
    # S1: Validate bearer token before doing anything else.
    # SESSION_TOKEN is generated at startup and stored in ~/.devpilot/session_token.txt.
    # Use secrets.compare_digest to prevent timing-based token guessing.
    if not token or not secrets.compare_digest(token.encode(), SESSION_TOKEN.encode()):
        await request.send_text(json.dumps({"type": "error", "message": "Unauthorized: invalid or missing token."}))
        await request.close(code=4401)
        return
    active_profile = config_manager.get_active_profile()

    # If no session_id provided, resume the last session for this workspace.
    resolved_session_id = session_id
    if not resolved_session_id and workspace_state.root:
        from ..db import get_fallback_session_id
        resolved_session_id = await get_fallback_session_id(workspace_state.root)

    from ..state import session_id_var
    session_id_var.set(resolved_session_id)
    session_workspace_root = workspace_state.root

    # ── Live chat logger ────────────────────────────────────────────────────
    chat_logger = ChatLogger(resolved_session_id or "unknown")

    async def send_to_client(data: dict):
        """Forward every message to the browser AND mirror it to the log file."""
        try:
            await request.send_text(json.dumps(data))
        except Exception:
            pass

        # ── Mirror to log file ──────────────────────────────────────────────
        evt = data.get("type", "")
        try:
            if evt == "thinking" and data.get("content"):
                chat_logger.log_thinking(data["content"])

            elif evt == "status":
                msg_txt = data.get("message", "")
                if data.get("status") == "tool_executing" and data.get("tool_call"):
                    tc = data["tool_call"]
                    chat_logger.log_tool_call(
                        tc.get("name", "unknown"),
                        tc.get("id", ""),
                        tc.get("args") or {}
                    )
                elif msg_txt:
                    chat_logger.log_status(msg_txt)

            elif evt == "tool_result":
                chat_logger.log_tool_result(
                    data.get("name", "unknown"),
                    data.get("tool_call_id", ""),
                    str(data.get("result", "")),
                    data.get("status", "success")
                )

            elif evt == "text_delta" and data.get("content"):
                chat_logger.log_ai_chunk(data["content"])

            elif evt == "session_done":
                chat_logger._close_ai_block_if_needed()
        except Exception as log_err:
            logger.debug(f"ChatLogger mirror error: {log_err}")

    session = AgentSession(
        session_workspace_root,
        active_profile,
        send_to_client,
        get_permission_manager(),
        session_id=resolved_session_id
    )
    await session.load_history_from_db()

    # Announce which session was resumed so the frontend can sync.
    await send_to_client({
        "type": "session_loaded",
        "session_id": session.session_id,
        "workspace_root": session_workspace_root,
        "message_count": len(session.conversation_history),
    })

    # Restore context memory from Redis / shared_memory if available
    try:
        from ..state import redis_client
        from ..shared_memory import sm_get_all
        workspace_id = os.path.basename(session_workspace_root) or "default"
        run_id = session.session_id or workspace_id
        raw = await redis_client.get(f"session:{workspace_id}:ctx")
        if raw:
            session.orchestrator.context.memory = json.loads(raw)
        else:
            mem = await sm_get_all(run_id)
            if not mem:
                mem = await sm_get_all(workspace_id)
            if mem:
                session.orchestrator.context.memory = mem
    except Exception as e:
        logger.error(f"Failed to restore context from Redis: {e}")
    
    async def heartbeat():
        while True:
            await asyncio.sleep(20)
            try:
                await request.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break

    hb_task = asyncio.create_task(heartbeat())
    try:
        from ..processes import global_process_manager
        while True:
            raw_msg = await request.receive_text()
            msg = json.loads(raw_msg)
            msg_type = msg.get("type")
            
            if msg_type == "pong":
                continue
                
            if msg_type == "user_message":
                text = msg.get("text", "")
                mode = msg.get("mode", "Ask")
                auto_apply = msg.get("auto_apply", False)
                # Optional editor context & attachments processing.
                open_languages = msg.get("open_languages") or []
                open_files = msg.get("open_files") or []
                attached_files = msg.get("attached_files") or []

                # Log user message immediately
                chat_logger.log_user(f"[{mode}] {text}")

                if isinstance(open_languages, list):
                    session.open_languages = [str(x) for x in open_languages if x]
                if isinstance(open_files, list):
                    session.open_files = [str(x) for x in open_files if x]

                # Process explicitly attached files via Vision / RAG pipeline
                if attached_files and isinstance(attached_files, list):
                    try:
                        from ..attachments import process_attachments, format_attachment_prompt
                        att_paths = [str(x) for x in attached_files if x]
                        att_results = await process_attachments(
                            att_paths, query=text, workspace_root=session.workspace_root
                        )
                        att_text = format_attachment_prompt(att_results)
                        if att_text:
                            text = text + "\n\n" + att_text
                    except Exception as att_err:
                        logger.error("Failed to process attached files in chat session: %s", att_err)

                # Do NOT update session.workspace_root from the global workspace_state here.
                # The session workspace was locked at connection open to prevent cross-session bleed.
                # Enqueue instead of cancel+replace — preserves in-flight work
                await session.enqueue_message(text, mode, auto_apply)

            elif msg_type == "change_workspace":
                # Explicit per-session workspace change from the UI
                new_root = msg.get("workspace_root", "").strip()
                if new_root and os.path.isdir(new_root):
                    session.workspace_root = new_root
                    logger.info(f"Session {session_id}: workspace changed to {new_root}")
                
            elif msg_type == "confirm_response":
                tool_call_id = msg.get("tool_call_id")
                approved = msg.get("approved", False)
                scope = msg.get("scope", "once")
                edited_command = msg.get("command", None)
                hunk_decisions = msg.get("hunk_decisions", None)
                session.resolve_confirmation(tool_call_id, approved, scope, edited_command, hunk_decisions)
                
            elif msg_type == "change_profile":
                new_profile = config_manager.get_active_profile()
                session.profile = new_profile
                
            elif msg_type == "cancel_generation":
                # Cancel current task AND flush all queued messages
                await session.cancel_all()
                for p in global_process_manager.get_running_processes():
                    await p.stop()
                await session.broadcast_processes_state()
                logger.info("Agent session cancelled by user (queue cleared).")
                
            elif msg_type == "stop_process":
                proc_id = msg.get("process_id")
                if proc_id:
                    await global_process_manager.stop_process(proc_id)
                else:
                    for p in global_process_manager.get_running_processes():
                        await p.stop()
                await session.broadcast_processes_state()

            elif msg_type == "retry":
                snapshot = session._failed_request or getattr(session, "_last_request_snapshot", None)
                if snapshot:
                    session.conversation_history = list(snapshot["history"])
                    session._failed_request = None
                    text = snapshot["text"]
                    mode = snapshot["mode"]
                    auto_apply = snapshot["auto_apply"]
                    await session.enqueue_message(text, mode, auto_apply)
                else:
                    logger.warning("No failed request snapshot available to retry.")

            elif msg_type == "continue":
                mode = getattr(session, "last_mode", "Agent")
                auto_apply = getattr(session, "auto_apply", False)
                await session.enqueue_message("Continue.", mode, auto_apply)

            elif msg_type == "resume":
                mode = getattr(session, "last_mode", "Agent")
                auto_apply = getattr(session, "auto_apply", False)
                await session.enqueue_message("Resume and continue the previous task.", mode, auto_apply)
                
    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
        # Bug 4: abort pending confirmations on disconnect
        for tc_id, item in list(session.pending_confirmations.items()):
            item["approved"] = False
            item["event"].set()
    except Exception as e:
        logger.error(f"Chat WebSocket error: {str(e)}")
    finally:
        hb_task.cancel()

