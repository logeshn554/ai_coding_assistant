import os

from fastapi import APIRouter, HTTPException, Request

from ..state import SESSION_TOKEN

router = APIRouter()

@router.get("/auth/token")
def get_auth_token(request: Request):
    client_host = request.client.host if request.client else None
    
    is_loopback = (
        client_host is None
        or client_host in ("127.0.0.1", "localhost", "::1", "testclient")
        or client_host.startswith("127.0.0.")
        or client_host.startswith("::ffff:127.0.0.")
    )
    
    if is_loopback:
        return {"token": SESSION_TOKEN}

    # Remote / non-loopback connection requires auth key verification
    auth_key_env = os.environ.get("DEVPILOT_AUTH_KEY") or os.environ.get("AUTH_KEY")
    req_key = (
        request.headers.get("X-Auth-Key")
        or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        or request.query_params.get("key", "")
    )

    if auth_key_env:
        import secrets
        if not req_key or not secrets.compare_digest(req_key.encode(), auth_key_env.encode()):
            raise HTTPException(status_code=403, detail="Forbidden: Invalid auth key for remote access")
    else:
        # Docker / remote mode without explicit AUTH_KEY requires passing SESSION_TOKEN directly
        import secrets
        if not req_key or not secrets.compare_digest(req_key.encode(), SESSION_TOKEN.encode()):
            raise HTTPException(status_code=403, detail="Forbidden: Remote token access requires X-Auth-Key or AUTH_KEY env configuration")

    return {"token": SESSION_TOKEN}

@router.post("/api/auth/ticket")
async def issue_ws_ticket(request: Request):
    from ..state import create_ws_ticket
    ticket = await create_ws_ticket()
    return {"ticket": ticket}

