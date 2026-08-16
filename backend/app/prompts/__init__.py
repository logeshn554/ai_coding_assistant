"""Prompt templates and helpers for the DevPilot agent."""

from .master import (
    AGENT_ORCHESTRATION_SECTION,
    DEVPILOT_MASTER_SYSTEM_PROMPT,
    render_system_prompt,
)
from .modes import (
    AGENT_MODE_INSTRUCTIONS,
    ASK_MODE_INSTRUCTIONS,
    PLAN_MODE_INSTRUCTIONS,
)

__all__ = [
    "AGENT_MODE_INSTRUCTIONS",
    "AGENT_ORCHESTRATION_SECTION",
    "ASK_MODE_INSTRUCTIONS",
    "DEVPILOT_MASTER_SYSTEM_PROMPT",
    "PLAN_MODE_INSTRUCTIONS",
    "render_system_prompt",
]
