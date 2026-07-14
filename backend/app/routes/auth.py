import os
from fastapi import APIRouter, Request, HTTPException
from ..state import SESSION_TOKEN

router = APIRouter()

@router.get("/auth/token")
def get_auth_token(request: Request):
    client_host = request.client.host if request.client else None
    
    is_remote_allowed = (
        os.environ.get("ALLOW_REMOTE", "false").lower() == "true"
        or os.environ.get("DOCKER_MODE", "false").lower() == "true"
    )
    
    # Allow local connections or if remote is explicitly allowed (e.g. inside Docker)
    is_local = (
        is_remote_allowed
        or client_host is None
        or client_host in ("127.0.0.1", "localhost", "::1", "testclient")
        or client_host.startswith("127.0.0.")
        or client_host.startswith("::ffff:127.0.0.")
    )
    if not is_local:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return {"token": SESSION_TOKEN}
