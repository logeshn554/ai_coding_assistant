import os
import json
import uuid
import datetime
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from ..state import workspace_state, config_manager, permission_manager, SESSION_TOKEN, logger
from ..db import async_session, SessionModel, MessageModel, get_active_session_id, set_active_session_id
from ..agent import AgentSession
from ..processes import global_process_manager
from ..utils import run_cmd_async

router = APIRouter()

class ChatHistoryRequest(BaseModel):
    messages: list

class ChatSessionCreateRequest(BaseModel):
    title: str

class ChatSessionRenameRequest(BaseModel):
    title: str

class ChatSessionSaveRequest(BaseModel):
    messages: list

@router.get("/api/chat/history")
async def get_chat_history():
    active_id = await get_active_session_id()
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
async def save_chat_history(req: ChatHistoryRequest):
    active_id = await get_active_session_id()
    try:
        async with async_session() as db:
            stmt = select(SessionModel).where(SessionModel.id == active_id)
            res = await db.execute(stmt)
            session = res.scalar()
            if not session:
                session = SessionModel(id=active_id, title="Default Conversation")
                db.add(session)
                
            del_stmt = delete(MessageModel).where(MessageModel.session_id == active_id)
            await db.execute(del_stmt)
            
            for m in req.messages:
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
            await db.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/chat/sessions")
async def get_chat_sessions():
    async with async_session() as db:
        stmt = select(SessionModel).order_by(SessionModel.updated_at.desc())
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        
        sessions_list = []
        for s in sessions:
            sessions_list.append({
                "id": s.id,
                "title": s.title,
                "created_at": int(s.created_at.timestamp()),
                "updated_at": int(s.updated_at.timestamp())
            })
        
        active_id = await get_active_session_id()
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
                title=req.title.strip() or "New Chat"
            )
            db.add(new_session)
            await db.commit()
            
            set_active_session_id(new_id)
            return {
                "success": True, 
                "session": {
                    "id": new_id,
                    "title": new_session.title,
                    "created_at": int(new_session.created_at.timestamp()),
                    "updated_at": int(new_session.updated_at.timestamp()),
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
        
        set_active_session_id(session_id)
        
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
async def delete_chat_session(session_id: str):
    try:
        async with async_session() as db:
            stmt = select(SessionModel).where(SessionModel.id == session_id)
            res = await db.execute(stmt)
            session = res.scalar()
            if not session:
                raise HTTPException(status_code=404, detail="Chat session not found")
            
            await db.delete(session)
            await db.commit()
            
            active_id = await get_active_session_id()
            if active_id == session_id:
                res_remaining = await db.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()))
                latest = res_remaining.scalars().first()
                if latest:
                    set_active_session_id(latest.id)
                else:
                    default_session = SessionModel(id="default-session", title="Default Conversation")
                    db.add(default_session)
                    await db.commit()
                    set_active_session_id("default-session")
                    
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/chat/sessions")
async def clear_all_sessions():
    try:
        async with async_session() as db:
            await db.execute(delete(SessionModel))
            default_session = SessionModel(id="default-session", title="Default Conversation")
            db.add(default_session)
            await db.commit()
            set_active_session_id("default-session")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def sync_get_workspace_stats(root_path: str):
    total_files = 0
    total_lines = 0
    languages = {}
    
    for root, dirs, files in os.walk(root_path):
        if any(d in root for d in {".git", "node_modules", "venv", "__pycache__", ".devpilot", "dist", "build"}):
            continue
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}:
                continue
            abs_path = os.path.join(root, f)
            total_files += 1
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                    lines = file_obj.readlines()
                    total_lines += len(lines)
            except Exception:
                pass
            
            lang_name = "Unknown"
            if ext == ".py": lang_name = "Python"
            elif ext in {".ts", ".tsx"}: lang_name = "TypeScript"
            elif ext in {".js", ".jsx"}: lang_name = "JavaScript"
            elif ext == ".json": lang_name = "JSON"
            elif ext == ".css": lang_name = "CSS"
            elif ext == ".html": lang_name = "HTML"
            elif ext == ".md": lang_name = "Markdown"
            
            languages[lang_name] = languages.get(lang_name, 0) + 1
            
    return total_files, total_lines, languages

@router.get("/api/workspace/stats")
async def get_workspace_stats():
    if not workspace_state.root:
        return {"total_files": 0, "total_lines": 0, "languages": {}, "git_commits": 0}
    try:
        loop = asyncio.get_running_loop()
        total_files, total_lines, languages = await loop.run_in_executor(
            None, sync_get_workspace_stats, workspace_state.root
        )

        git_commits = 0
        try:
            commits_out = await run_cmd_async("git rev-list --count HEAD", workspace_state.root)
            if "fatal:" not in commits_out:
                git_commits = int(commits_out.strip())
        except Exception:
            pass

        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "languages": languages,
            "git_commits": git_commits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: Optional[str] = Query(None)):
    ws_token = token or websocket.query_params.get("token") or websocket.headers.get("x-session-token")
    if not ws_token or ws_token != SESSION_TOKEN:
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return
        
    await websocket.accept()
    active_profile = config_manager.get_active_profile()
    
    async def send_to_client(data: dict):
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass
            
    session = AgentSession(workspace_state.root, active_profile, send_to_client, permission_manager)
    
    try:
        while True:
            raw_msg = await websocket.receive_text()
            msg = json.loads(raw_msg)
            msg_type = msg.get("type")
            
            if msg_type == "user_message":
                text = msg.get("text", "")
                mode = msg.get("mode", "Ask")
                auto_apply = msg.get("auto_apply", False)
                session.workspace_root = workspace_state.root
                if session.active_task and not session.active_task.done():
                    session.active_task.cancel()
                session.active_task = asyncio.create_task(session.handle_user_message(text, mode, auto_apply))
                
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
                if session.active_task and not session.active_task.done():
                    session.active_task.cancel()
                    logger.info("Agent session task cancelled by user request.")
                for p in global_process_manager.get_running_processes():
                    await p.stop()
                await session.broadcast_processes_state()
                
            elif msg_type == "stop_process":
                proc_id = msg.get("process_id")
                if proc_id:
                    await global_process_manager.stop_process(proc_id)
                else:
                    for p in global_process_manager.get_running_processes():
                        await p.stop()
                await session.broadcast_processes_state()
                
    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {str(e)}")
