import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..state import config_manager

router = APIRouter()

VALID_SHELLS = {"", "cmd", "powershell", "bash", "sh"}


class SettingsUpdateRequest(BaseModel):
    exclude_list: list
    auto_backup_enabled: bool
    agent_model_name: Optional[str] = ""
    agent_models: Optional[dict] = None
    # Terminal preferences
    default_shell: Optional[str] = ""
    terminal_font_size: Optional[int] = Field(default=13, ge=8, le=32)
    terminal_scrollback: Optional[int] = Field(default=5000, ge=500, le=100000)


@router.get("/api/config/settings")
def get_settings():
    return {
        "exclude_list": config_manager.get_exclude_list(),
        "auto_backup_enabled": config_manager.get_auto_backup_enabled(),
        "agent_model_name": config_manager.get_agent_model_name(),
        "agent_models": config_manager.get_agent_models(),
        # Terminal preferences
        "default_shell": config_manager.get_default_shell(),
        "terminal_font_size": config_manager.get_terminal_font_size(),
        "terminal_scrollback": config_manager.get_terminal_scrollback(),
    }


@router.post("/api/config/settings")
def save_settings(req: SettingsUpdateRequest):
    try:
        config_manager.set_exclude_list(req.exclude_list)
        config_manager.set_auto_backup_enabled(req.auto_backup_enabled)
        config_manager.set_agent_model_name(req.agent_model_name)
        if req.agent_models is not None:
            config_manager.set_agent_models(req.agent_models)
        # Terminal preferences
        shell = req.default_shell or ""
        if shell not in VALID_SHELLS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid shell '{shell}'. Must be one of: {sorted(VALID_SHELLS)}"
            )
        config_manager.set_default_shell(shell)
        if req.terminal_font_size is not None:
            config_manager.set_terminal_font_size(req.terminal_font_size)
        if req.terminal_scrollback is not None:
            config_manager.set_terminal_scrollback(req.terminal_scrollback)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

