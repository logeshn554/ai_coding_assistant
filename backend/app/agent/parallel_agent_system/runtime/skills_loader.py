"""Skills loader for the parallel agent system.

Delegates to ``backend/app/skills_loader`` for all matching logic so that
alias maps and scoring rules stay in a single place — this module is a thin
adapter that bridges the workspace root to the parallel agent runtime.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("parallel_agent_system.skills_loader")

# ---------------------------------------------------------------------------
# Make backend importable when parallel_agent_system is used in isolation.
# ---------------------------------------------------------------------------
def _ensure_backend_on_path() -> None:
    """Add the backend directory to sys.path if it is not already present."""
    repo_root = Path(__file__).resolve().parents[2]
    backend_path = str(repo_root / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


_ensure_backend_on_path()


class SkillsLoader:
    """Load and score skills.md sections for a given task description.

    Reuses the matching logic from ``backend/app/skills_loader`` — the alias
    maps and scoring functions are defined there and shared here rather than
    duplicated.
    """

    # Path to the workspace root.  Can be overridden for testing.
    workspace_root: str = str(Path(__file__).resolve().parents[2])

    @classmethod
    def load_for_task(cls, task_description: str) -> str:
        """Return relevant skills.md content scored against *task_description*.

        This method replaces the previous hardcoded skeleton.  It:
        1. Parses the workspace ``skills.md`` via the shared backend loader.
        2. Infers language hints from keywords in *task_description*.
        3. Runs ``select_relevant_sections`` with those hints.
        4. Formats and returns only the matching sections.

        Args:
            task_description: Free-form description of the current task.
                The matcher scores section names against keywords derived
                from this string.

        Returns:
            Formatted markdown string of relevant skills sections, or an empty
            string when ``skills.md`` does not exist or nothing matches.
        """
        try:
            from app.skills_loader import (
                _LANGUAGE_ALIASES,
                format_skills_for_prompt,
                load_skills,
                select_relevant_sections,
            )
        except ImportError:
            logger.warning(
                "Could not import backend skills_loader — returning empty skills."
            )
            return ""

        sections = load_skills(cls.workspace_root)
        if not sections:
            return ""

        # Derive language hints from the task description by checking alias keys
        # and their synonym tuples for matches.
        desc_lower = task_description.lower()
        inferred_languages: list[str] = []
        for lang_key, aliases in _LANGUAGE_ALIASES.items():
            keywords = (lang_key,) + (aliases if isinstance(aliases, tuple) else (aliases,))
            if any(kw in desc_lower for kw in keywords):
                # Capitalise to match the display-name convention used by
                # select_relevant_sections / _section_matches_language.
                inferred_languages.append(lang_key.capitalize())

        relevant = select_relevant_sections(sections, inferred_languages or None)
        return format_skills_for_prompt(relevant)
