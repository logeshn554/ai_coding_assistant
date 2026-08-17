from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..state import config_manager

router = APIRouter()

VALID_SHELLS = {"", "cmd", "powershell", "bash", "sh"}


class SettingsUpdateRequest(BaseModel):
    exclude_list: list
    auto_backup_enabled: bool
    auto_inspect_on_server_start: bool | None = False
    agent_model_name: str | None = ""
    agent_models: dict | None = None
    agent_profiles: dict | None = None
    image_analysis_model: str | None = ""
    image_analysis_mode: str | None = "auto"
    secondary_agent_model: str | None = ""
    primary_agent_profile: str | None = ""
    secondary_agent_profile: str | None = ""
    mcp_servers: list | None = None
    # Web Search Fallback settings
    web_search_fallback_enabled: bool | None = False
    repeat_error_threshold: int | None = Field(default=2, ge=1, le=10)
    tavily_api_key: str | None = ""
    # Terminal preferences
    default_shell: str | None = ""
    terminal_font_size: int | None = Field(default=13, ge=8, le=32)
    terminal_scrollback: int | None = Field(default=5000, ge=500, le=100000)
    # Agent Behavior & Local Permissions
    artifact_review_policy: str | None = "Always Ask"
    file_access_rules: list | None = None
    network_access_rules: list | None = None
    terminal_command_rules: list | None = None
    unsandboxed_command_rules: list | None = None
    mcp_tool_rules: list | None = None
    loopix_rpm: int | None = Field(default=15, ge=1)
    concurrency_mode: str | None = "parallel"
    temperature: float | None = Field(default=1.0, ge=0.0, le=2.0)
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=16384, ge=1, le=1000000)
    seed: int | None = Field(default=42)
    stream: bool | None = True
    decision_engine: str | None = "rule_based"
    dual_llm_mode: bool | None = False


@router.get("/api/config/settings")
def get_settings():
    return {
        "exclude_list": config_manager.get_exclude_list(),
        "auto_backup_enabled": config_manager.get_auto_backup_enabled(),
        "auto_inspect_on_server_start": config_manager.get_auto_inspect_on_server_start(),
        "agent_model_name": config_manager.get_agent_model_name(),
        "secondary_agent_model": config_manager.get_secondary_agent_model(),
        "primary_agent_profile": config_manager.get_primary_agent_profile(),
        "secondary_agent_profile": config_manager.get_secondary_agent_profile(),
        "agent_models": config_manager.get_agent_models(),
        "agent_profiles": config_manager.get_agent_profiles(),
        "image_analysis_model": config_manager.get_image_analysis_model(),
        "image_analysis_mode": config_manager.get_image_analysis_mode(),
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
        "loopix_rpm": config_manager.get_loopix_rpm(),
        "concurrency_mode": config_manager.get_concurrency_mode(),
        "temperature": config_manager.get_temperature(),
        "top_p": config_manager.get_top_p(),
        "max_tokens": config_manager.get_max_tokens(),
        "seed": config_manager.get_seed(),
        "stream": config_manager.get_stream(),
        "decision_engine": config_manager.get_decision_engine(),
        "dual_llm_mode": config_manager.get_dual_llm_mode(),
    }


@router.post("/api/config/settings")
def save_settings(req: SettingsUpdateRequest):
    try:
        config_manager.set_exclude_list(req.exclude_list)
        config_manager.set_auto_backup_enabled(req.auto_backup_enabled)
        if req.auto_inspect_on_server_start is not None:
            config_manager.set_auto_inspect_on_server_start(req.auto_inspect_on_server_start)
        config_manager.set_agent_model_name(req.agent_model_name)
        if req.secondary_agent_model is not None:
            config_manager.set_secondary_agent_model(req.secondary_agent_model)
        if req.primary_agent_profile is not None:
            config_manager.set_primary_agent_profile(req.primary_agent_profile)
        if req.secondary_agent_profile is not None:
            config_manager.set_secondary_agent_profile(req.secondary_agent_profile)
        if req.agent_models is not None:
            config_manager.set_agent_models(req.agent_models)
        if req.agent_profiles is not None:
            config_manager.set_agent_profiles(req.agent_profiles)
        if req.image_analysis_model is not None:
            config_manager.set_image_analysis_model(req.image_analysis_model)
        if req.image_analysis_mode is not None:
            config_manager.set_image_analysis_mode(req.image_analysis_mode)

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
        if req.loopix_rpm is not None:
            config_manager.set_loopix_rpm(req.loopix_rpm)
        if req.concurrency_mode is not None:
            config_manager.set_concurrency_mode(req.concurrency_mode)
        if req.temperature is not None:
            config_manager.set_temperature(req.temperature)
        if req.top_p is not None:
            config_manager.set_top_p(req.top_p)
        if req.max_tokens is not None:
            config_manager.set_max_tokens(req.max_tokens)
        if req.seed is not None:
            config_manager.set_seed(req.seed)
        else:
            config_manager.set_seed(None)
        if req.stream is not None:
            config_manager.set_stream(req.stream)
        if req.decision_engine is not None:
            config_manager.set_decision_engine(req.decision_engine)
        if req.dual_llm_mode is not None:
            config_manager.set_dual_llm_mode(req.dual_llm_mode)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


