"""HTTP routes for workspace skills.md."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from ..skills_loader import (
    _LANGUAGE_ALIASES,
    format_skills_for_prompt,
    load_skills,
    select_relevant_sections,
)
from ..state import workspace_state

logger = logging.getLogger("loopix.routes.skills")
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


@router.get("/api/skills/match")
def match_skills(task: str = Query(..., description="Free-form task description to score against skills sections.")):
    """Return only the skills.md sections relevant to *task*.

    Scores the task description against section names using the same alias-map
    and language-keyword logic used at prompt-build time, so callers can
    request only the sections they need without pulling the entire file.

    Args:
        task: Free-form description of the current task (query parameter).

    Returns:
        JSON object with:
        - ``sections``: matched section name → body map.
        - ``formatted``: pre-formatted prompt-ready block (may be empty).
        - ``inferred_languages``: language keywords detected in *task*.
    """
    root = workspace_state.root or ""
    try:
        all_sections = load_skills(root)
    except Exception as exc:
        logger.warning("Failed to load skills for workspace %s: %s", root, exc)
        all_sections = {}

    if not all_sections:
        return {"sections": {}, "formatted": "", "inferred_languages": []}

    # Infer language hints from the task string.
    desc_lower = task.lower()
    inferred_languages: list[str] = []
    for lang_key, aliases in _LANGUAGE_ALIASES.items():
        keywords = (lang_key,) + (aliases if isinstance(aliases, tuple) else (aliases,))
        if any(kw in desc_lower for kw in keywords):
            inferred_languages.append(lang_key.capitalize())

    matched = select_relevant_sections(all_sections, inferred_languages or None)
    formatted = format_skills_for_prompt(matched)

    return {
        "sections": matched,
        "formatted": formatted,
        "inferred_languages": inferred_languages,
    }
