"""Backward-compatible re-exports from modular agent package. """
from .prompts.master import AGENT_ORCHESTRATION_SECTION, LOOPIX_MASTER_SYSTEM_PROMPT
from .prompts.modes import (
    AGENT_MODE_INSTRUCTIONS,
    ASK_MODE_INSTRUCTIONS,
    PLAN_MODE_INSTRUCTIONS,
)
from .session.agent_session import AgentSession

__all__ = [
    "AGENT_MODE_INSTRUCTIONS",
    "AGENT_ORCHESTRATION_SECTION",
    "ASK_MODE_INSTRUCTIONS",
    "LOOPIX_MASTER_SYSTEM_PROMPT",
    "PLAN_MODE_INSTRUCTIONS",
    "AgentSession",
]
