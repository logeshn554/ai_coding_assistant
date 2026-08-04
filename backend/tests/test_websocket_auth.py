import os
import sys
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app, SESSION_TOKEN

def test_websocket_chat_auth():
    client = TestClient(app)
    
    # 1. Test connection with missing token
    with client.websocket_connect("/ws/chat") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "message": "Unauthorized: invalid or missing token."}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401

    # 2. Test connection with invalid token
    with client.websocket_connect("/ws/chat?token=wrong_token") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "message": "Unauthorized: invalid or missing token."}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401

    # 3. Test connection with valid token
    with client.websocket_connect(f"/ws/chat?token={SESSION_TOKEN}") as ws:
        pass

def test_websocket_terminal_auth():
    client = TestClient(app)
    
    # 1. Test connection with missing token
    with client.websocket_connect("/ws/terminal") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "message": "Unauthorized: invalid or missing token."}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401

    # 2. Test connection with invalid token
    with client.websocket_connect("/ws/terminal?token=wrong_token") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "message": "Unauthorized: invalid or missing token."}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401

    # 3. Test connection with valid token
    with client.websocket_connect(f"/ws/terminal?token={SESSION_TOKEN}") as ws:
        pass

def test_websocket_lsp_auth():
    client = TestClient(app)
    
    # 1. Test connection with missing token
    with client.websocket_connect("/ws/lsp/python") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "message": "Unauthorized: invalid or missing token."}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401

    # 2. Test connection with invalid token
    with client.websocket_connect("/ws/lsp/python?token=wrong_token") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "error", "message": "Unauthorized: invalid or missing token."}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4401

    # 3. Test connection with valid token but unsupported language
    with client.websocket_connect(f"/ws/lsp/invalid_lang?token={SESSION_TOKEN}") as ws:
        msg = ws.receive_json()
        assert "Unsupported language" in msg.get("error", "")
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
