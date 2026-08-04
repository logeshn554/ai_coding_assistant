import asyncio
import json
import secrets
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from ..state import workspace_state, SESSION_TOKEN, logger
from ..terminal import TerminalManager

router = APIRouter()

@router.websocket("/ws/terminal")
async def websocket_terminal(
    websocket: WebSocket,
    ticket: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    shell: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    await websocket.accept()
    from ..state import verify_ws_ticket
    is_authenticated = False
    if ticket and verify_ws_ticket(ticket):
        is_authenticated = True
    elif token and secrets.compare_digest(token.encode(), SESSION_TOKEN.encode()):
        is_authenticated = True

    if not is_authenticated:
        await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized: invalid or missing token."}))
        await websocket.close(code=4401)
        return
    
    # NOTE: app.middleware("http") does NOT run for websocket connections,
    # so session_id_var is never populated here by session_middleware.
    # Set it explicitly from the query param so workspace_state.root resolves
    # to this session's actual opened folder instead of the global default.
    from ..state import session_id_var
    session_token = session_id_var.set(session_id)
    
    async def send_to_client(data: str):
        try:
            await websocket.send_text(data)
        except Exception:
            pass
            
    term_manager = TerminalManager(workspace_state.root, send_to_client, shell=shell)

    # Wait for an initial resize message from the frontend before starting the PTY.
    # This ensures the PTY is created with the correct terminal dimensions.
    # If the first message isn't a resize, start with defaults and treat it as input.
    initial_cols, initial_rows = 120, 30
    first_data = None
    try:
        raw = await websocket.receive_text()
        try:
            msg = json.loads(raw)
            if isinstance(msg, dict) and msg.get("type") == "resize":
                initial_cols = msg.get("cols", 120)
                initial_rows = msg.get("rows", 30)
            else:
                first_data = raw  # Not a resize — treat as input after start
        except (json.JSONDecodeError, TypeError):
            first_data = raw
    except WebSocketDisconnect:
        session_id_var.reset(session_token)
        return

    await term_manager.start(cols=initial_cols, rows=initial_rows)

    # If the first message was input (not resize), forward it now
    if first_data is not None:
        await term_manager.write(first_data)
    
    async def heartbeat():
        while True:
            await asyncio.sleep(20)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break

    hb_task = asyncio.create_task(heartbeat())
    try:
        while True:
            raw = await websocket.receive_text()
            
            # Check if this is a JSON control message (resize, etc.)
            if raw.startswith("{"):
                try:
                    msg = json.loads(raw)
                    if isinstance(msg, dict):
                        if msg.get("type") == "resize":
                            cols = msg.get("cols", 120)
                            rows = msg.get("rows", 30)
                            await term_manager.resize(cols, rows)
                            continue
                        elif msg.get("type") == "pong":
                            continue
                except (json.JSONDecodeError, TypeError):
                    pass  # Not valid JSON — treat as regular terminal input
            
            # Regular terminal input — forward to the PTY
            await term_manager.write(raw)
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected")
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {str(e)}")
    finally:
        hb_task.cancel()
        await term_manager.stop()
        if session_id:
            workspace_state.evict_session(session_id)
        session_id_var.reset(session_token)
