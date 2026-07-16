import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from ..state import workspace_state, SESSION_TOKEN, logger
from ..terminal import TerminalManager

router = APIRouter()

@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket, token: Optional[str] = Query(None), shell: Optional[str] = Query(None)):
    ws_token = token or websocket.query_params.get("token") or websocket.headers.get("x-session-token")
    if not ws_token or ws_token != SESSION_TOKEN:
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return
        
    await websocket.accept()
    
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
        return

    await term_manager.start(cols=initial_cols, rows=initial_rows)

    # If the first message was input (not resize), forward it now
    if first_data is not None:
        await term_manager.write(first_data)
    
    try:
        while True:
            raw = await websocket.receive_text()
            
            # Check if this is a JSON control message (resize, etc.)
            if raw.startswith("{"):
                try:
                    msg = json.loads(raw)
                    if isinstance(msg, dict) and msg.get("type") == "resize":
                        cols = msg.get("cols", 120)
                        rows = msg.get("rows", 30)
                        await term_manager.resize(cols, rows)
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
        await term_manager.stop()
