from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from ..state import workspace_state, SESSION_TOKEN, logger
from ..terminal import TerminalManager

router = APIRouter()

@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket, token: Optional[str] = Query(None)):
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
            
    term_manager = TerminalManager(workspace_state.root, send_to_client)
    await term_manager.start()
    
    try:
        while True:
            data = await websocket.receive_text()
            await term_manager.write(data)
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected")
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {str(e)}")
    finally:
        await term_manager.stop()
