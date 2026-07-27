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
    auto_inspect_on_server_start: Optional[bool] = False
    agent_model_name: Optional[str] = ""
    agent_models: Optional[dict] = None
    image_analysis_model: Optional[str] = ""
    mcp_servers: Optional[list] = None
    # Web Search Fallback settings
    web_search_fallback_enabled: Optional[bool] = False
    repeat_error_threshold: Optional[int] = Field(default=2, ge=1, le=10)
    tavily_api_key: Optional[str] = ""
    # Terminal preferences
    default_shell: Optional[str] = ""
    terminal_font_size: Optional[int] = Field(default=13, ge=8, le=32)
    terminal_scrollback: Optional[int] = Field(default=5000, ge=500, le=100000)
    # Agent Behavior & Local Permissions
    artifact_review_policy: Optional[str] = "Always Ask"
    file_access_rules: Optional[list] = None
    network_access_rules: Optional[list] = None
    terminal_command_rules: Optional[list] = None
    unsandboxed_command_rules: Optional[list] = None
    mcp_tool_rules: Optional[list] = None


@router.get("/api/config/settings")
def get_settings():
    return {
        "exclude_list": config_manager.get_exclude_list(),
        "auto_backup_enabled": config_manager.get_auto_backup_enabled(),
        "auto_inspect_on_server_start": config_manager.get_auto_inspect_on_server_start(),
        "agent_model_name": config_manager.get_agent_model_name(),
        "agent_models": config_manager.get_agent_models(),
        "image_analysis_model": config_manager.get_image_analysis_model(),
        "mcp_servers": config_manager.get_mcp_servers(),
        "web_search_fallback_enabled": config_manager.get_web_search_fallback_enabled(),
        "repeat_error_threshold": config_manager.get_repeat_error_threshold(),
        "tavily_api_key": config_manager.get_tavily_api_key(),
        # Terminal preferences
        "default_shell": config_manager.get_default_shell(),
        "terminal_font_size": config_manager.get_terminal_font_size(),
        "terminal_scrollback": config_manager.get_terminal_scrollback(),
        # Agent Behavior & Local Permissions
        "artifact_review_policy": config_manager.get_artifact_review_policy(),
        "file_access_rules": config_manager.get_file_access_rules(),
        "network_access_rules": config_manager.get_network_access_rules(),
        "terminal_command_rules": config_manager.get_terminal_command_rules(),
        "unsandboxed_command_rules": config_manager.get_unsandboxed_command_rules(),
        "mcp_tool_rules": config_manager.get_mcp_tool_rules(),
    }


@router.post("/api/config/settings")
def save_settings(req: SettingsUpdateRequest):
    try:
        config_manager.set_exclude_list(req.exclude_list)
        config_manager.set_auto_backup_enabled(req.auto_backup_enabled)
        if req.auto_inspect_on_server_start is not None:
            config_manager.set_auto_inspect_on_server_start(req.auto_inspect_on_server_start)
        config_manager.set_agent_model_name(req.agent_model_name)
        if req.agent_models is not None:
            config_manager.set_agent_models(req.agent_models)
        if req.image_analysis_model is not None:
            config_manager.set_image_analysis_model(req.image_analysis_model)
        if req.mcp_servers is not None:
            config_manager.set_mcp_servers(req.mcp_servers)
        if req.web_search_fallback_enabled is not None:
            config_manager.set_web_search_fallback_enabled(req.web_search_fallback_enabled)
        if req.repeat_error_threshold is not None:
            config_manager.set_repeat_error_threshold(req.repeat_error_threshold)
        if req.tavily_api_key is not None:
            config_manager.set_tavily_api_key(req.tavily_api_key)
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
        # Agent Behavior & Local Permissions
        if req.artifact_review_policy is not None:
            config_manager.set_artifact_review_policy(req.artifact_review_policy)
        if req.file_access_rules is not None:
            config_manager.set_file_access_rules(req.file_access_rules)
        if req.network_access_rules is not None:
            config_manager.set_network_access_rules(req.network_access_rules)
        if req.terminal_command_rules is not None:
            config_manager.set_terminal_command_rules(req.terminal_command_rules)
        if req.unsandboxed_command_rules is not None:
            config_manager.set_unsandboxed_command_rules(req.unsandboxed_command_rules)
        if req.mcp_tool_rules is not None:
            config_manager.set_mcp_tool_rules(req.mcp_tool_rules)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


