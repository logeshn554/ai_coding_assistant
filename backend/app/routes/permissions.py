from fastapi import APIRouter
from pydantic import BaseModel

from ..permissions import DEFAULT_POLICY_MATRIX, Capability
from ..state import config_manager, get_permission_manager

router = APIRouter()

class PermissionGrantRequest(BaseModel):
    command: str
    scope: str

class PermissionRevokeRequest(BaseModel):
    command: str
    scope: str  # "session" or "project"

class PolicyUpdateRequest(BaseModel):
    policy: str
    custom_matrix: dict[str, bool] | None = None

@router.get("/api/permissions")
def get_permissions():
    pm = get_permission_manager()
    project_id = pm._get_project_id()
    project_perms = config_manager.get_project_permissions(project_id)
    session_perms = list(pm.session_permissions)
    return {
        "project": project_perms,
        "session": session_perms,
        "policy": pm.active_policy,
        "capabilities": [c.value for c in Capability]
    }

@router.get("/api/permissions/policy")
def get_policy():
    pm = get_permission_manager()
    return {
        "active_policy": pm.active_policy,
        "matrix": DEFAULT_POLICY_MATRIX.get(pm.active_policy, {}),
        "custom_overrides": pm.custom_overrides,
        "all_presets": list(DEFAULT_POLICY_MATRIX.keys()) + ["Custom"]
    }

@router.post("/api/permissions/policy")
def set_policy(req: PolicyUpdateRequest):
    pm = get_permission_manager()
    pm.set_policy(req.policy, req.custom_matrix)
    return {
        "success": True,
        "active_policy": pm.active_policy
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
