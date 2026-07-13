import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import config_manager

router = APIRouter()

class SettingsUpdateRequest(BaseModel):
    exclude_list: list
    auto_backup_enabled: bool
    agent_model_name: Optional[str] = ""
    agent_models: Optional[dict] = None

@router.get("/api/config/settings")
def get_settings():
    return {
        "exclude_list": config_manager.get_exclude_list(),
        "auto_backup_enabled": config_manager.get_auto_backup_enabled(),
        "agent_model_name": config_manager.get_agent_model_name(),
        "agent_models": config_manager.get_agent_models()
    }

@router.post("/api/config/settings")
def save_settings(req: SettingsUpdateRequest):
    try:
        config_manager.set_exclude_list(req.exclude_list)
        config_manager.set_auto_backup_enabled(req.auto_backup_enabled)
        config_manager.set_agent_model_name(req.agent_model_name)
        if req.agent_models is not None:
            config_manager.set_agent_models(req.agent_models)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
