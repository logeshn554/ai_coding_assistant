import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import workspace_state, permission_manager, config_manager

logger = logging.getLogger("devpilot.routes.workspace")
router = APIRouter()

class WorkspaceChangeRequest(BaseModel):
    path: str

@router.get("/api/workspace")
def get_workspace():
    return {"workspace": workspace_state.root}

@router.get("/api/shell/name")
def get_shell_name():
    from ..shell_adapter import ShellAdapter
    return {"name": ShellAdapter.get_shell_name()}

@router.post("/api/workspace/change")
def change_workspace(req: WorkspaceChangeRequest):
    try:
        if req.path == "":
            workspace_state.root = ""
            permission_manager.workspace_root = ""
            config_manager.set_last_workspace("")
            logger.info("Workspace closed.")
            return {"success": True, "workspace": ""}
            
        path = os.path.abspath(req.path)
        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail=f"Directory '{req.path}' does not exist.")
        workspace_state.root = path
        permission_manager.workspace_root = path
        logger.info(f"Workspace changed to: {workspace_state.root}")
        config_manager.set_last_workspace(workspace_state.root)
        return {"success": True, "workspace": workspace_state.root}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
