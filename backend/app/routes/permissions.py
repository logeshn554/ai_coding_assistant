import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import get_permission_manager, config_manager

router = APIRouter()

class PermissionGrantRequest(BaseModel):
    command: str
    scope: str

class PermissionRevokeRequest(BaseModel):
    command: str
    scope: str  # "session" or "project"

@router.get("/api/permissions")
def get_permissions():
    pm = get_permission_manager()
    project_id = pm._get_project_id()
    project_perms = config_manager.get_project_permissions(project_id)
    session_perms = list(pm.session_permissions)
    return {
        "project": project_perms,
        "session": session_perms
    }

@router.post("/api/permissions/grant")
def grant_permission(req: PermissionGrantRequest):
    get_permission_manager().grant_permission(req.command, req.scope)
    return {"success": True}

@router.post("/api/permissions/revoke")
def revoke_permission(req: PermissionRevokeRequest):
    pm = get_permission_manager()
    if req.scope == "session":
        cmd_pattern = pm._get_command_pattern(req.command)
        if cmd_pattern in pm.session_permissions:
            pm.session_permissions.remove(cmd_pattern)
    elif req.scope == "project":
        pm.revoke_project_permission(req.command)
    return {"success": True}
