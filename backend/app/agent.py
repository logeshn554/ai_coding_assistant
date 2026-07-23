"""Backward-compatible re-exports from modular agent package. """
from .session.agent_session import AgentSession
from .prompts.master import DEVPILOT_MASTER_SYSTEM_PROMPT, AGENT_ORCHESTRATION_SECTION
from .prompts.modes import ASK_MODE_INSTRUCTIONS, PLAN_MODE_INSTRUCTIONS, AGENT_MODE_INSTRUCTIONS

__all__ = [
    "AgentSession",
    "DEVPILOT_MASTER_SYSTEM_PROMPT",
    "ASK_MODE_INSTRUCTIONS",
    "PLAN_MODE_INSTRUCTIONS",
    "AGENT_MODE_INSTRUCTIONS",
    "AGENT_ORCHESTRATION_SECTION",
]
