"""HTTP routes for workspace skills.md."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..skills_loader import load_skills
from ..state import workspace_state

logger = logging.getLogger("devpilot.routes.skills")
router = APIRouter()


@router.get("/api/skills")
def get_skills():
    """Return parsed skills.md sections for the current workspace.

    Returns:
        JSON object with a ``sections`` map (empty when no skills.md).
    """
    root = workspace_state.root or ""
    try:
        sections = load_skills(root)
    except Exception as exc:
        logger.warning("Failed to load skills for workspace %s: %s", root, exc)
        sections = {}
    return {"sections": sections}
