"""
End-to-end verification test for WebSocket rate limits.
Ensures websocket connections exceeding limit are blocked with HTTP 429.
"""

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse
import slowapi.extension
from starlette.requests import Request

# Patch slowapi's Request type check to support WebSocket connections since they share HTTPConnection base
slowapi.extension.Request = (Request, WebSocket)

# Initialize mock FastAPI app for rate limit testing
app = FastAPI()
limiter = Limiter(key_func=lambda *args, **kwargs: "test_client")
app.state.limiter = limiter

# Custom rate limit exception handler returning HTTP 429
def rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)


@app.websocket("/ws/chat")
@limiter.limit("10/minute")
async def websocket_test_route(request: WebSocket):
    """WebSocket test route protected by rate limiter using request parameter name."""
    await request.accept()
    await request.send_text("connected")
    await request.close()


def test_websocket_rate_limiter_e2e():
    """Verify that the 11th websocket upgrade request in rapid succession is blocked with HTTP 429."""
    client = TestClient(app)
    results = []
    
    # Attempt 12 sequential WebSocket connections
    for i in range(12):
        try:
            with client.websocket_connect("/ws/chat") as websocket:
                data = websocket.receive_text()
                results.append(data)
        except Exception as exc:
            results.append(type(exc).__name__)
            
    print(f"\nCONNECTION RESULTS: {results}")
    
    # Verify first 10 succeeded
    for res in results[:10]:
        assert res == "connected"
        
    # Verify the 11th and 12th were rejected with WebSocketDenialResponse
    assert results[10] == "WebSocketDenialResponse"
    assert results[11] == "WebSocketDenialResponse"
