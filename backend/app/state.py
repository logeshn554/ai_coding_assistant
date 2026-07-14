import os
import secrets
import logging
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from .config import ConfigManager
from .permissions import PermissionManager

# Setup Logging
logger = logging.getLogger("devpilot.state")

# Generate session token and setup auth
SESSION_TOKEN = secrets.token_hex(32)

# Initialize slowapi rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# Initialize Config Manager
config_manager = ConfigManager()

# Default to the environment variable, persistent last workspace, or empty string
INITIAL_WORKSPACE_ROOT = os.environ.get("INITIAL_WORKSPACE_ROOT") or config_manager.get_last_workspace() or ""

class WorkspaceState:
    def __init__(self, initial_root: str):
        self.root = initial_root

workspace_state = WorkspaceState(INITIAL_WORKSPACE_ROOT)

# Initialize Permission Manager
permission_manager = PermissionManager(config_manager, workspace_state.root)

async def verify_token(request: Request = None):
    if request is None:
        return
    if request.scope.get("type") == "websocket":
        return
        
    path = request.url.path
    if path == "/auth/token" or not path.startswith("/api/"):
        return
        
    token = request.query_params.get("token")
    if not token:
        token = request.headers.get("X-Session-Token")
        
    if not token or token != SESSION_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
