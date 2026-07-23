"""Load and select workspace skills.md sections for agent system prompts."""

from __future__ import annotations

import logging
import os
import re
from typing import Iterable

logger = logging.getLogger("devpilot.skills_loader")

# Sections whose names match these (case-insensitive) are always included.
_ALWAYS_INCLUDE_NAMES = frozenset({"general", "all"})

# Cap when injecting all / unmatched sections to keep prompts bounded.
_DEFAULT_MAX_SECTIONS = 12
_DEFAULT_MAX_CHARS = 12_000

# Map common language labels / extensions to keywords for section matching.
_LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python", "py", "fastapi", "django", "flask"),
    "javascript": ("javascript", "js", "node", "nodejs"),
    "typescript": ("typescript", "ts", "tsx", "react"),
    "react": ("react", "tsx", "jsx", "typescript", "javascript"),
    "html": ("html", "markup"),
    "css": ("css", "scss", "sass", "styles"),
    "go": ("go", "golang"),
    "rust": ("rust", "rs"),
    "java": ("java"),
    "c++": ("c++", "cpp", "cplusplus"),
    "c": ("c", "clang"),
    "c#": ("c#", "csharp", "dotnet"),
    "ruby": ("ruby", "rb"),
    "php": ("php"),
    "kotlin": ("kotlin", "kt"),
    "swift": ("swift"),
    "shell": ("shell", "bash", "sh", "powershell"),
    "docker": ("docker", "dockerfile", "container"),
    "markdown": ("markdown", "md"),
    "json": ("json"),
    "yaml": ("yaml", "yml"),
    "sql": ("sql", "database", "postgres", "mysql"),
}

_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "Shell",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".sql": "SQL",
    ".dockerfile": "Docker",
}


def parse_skills_md(content: str) -> dict[str, str]:
    """Parse a skills.md document into ``##`` section name → body content.

    Args:
        content: Raw markdown text of a skills.md file.

    Returns:
        Mapping of section heading text (without ``##``) to stripped body
        content. Content before the first ``##`` heading is discarded.
    """
    if not content or not content.strip():
        return {}

    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = heading.group(1).strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()

    return sections


def load_skills(workspace_root: str) -> dict[str, str]:
    """Load and parse ``skills.md`` from a workspace root.

    Args:
        workspace_root: Absolute or relative path to the workspace directory.
            When empty or missing, returns an empty dict.

    Returns:
        Parsed section map, or ``{}`` if the file is missing or unreadable.
    """
    if not workspace_root or not str(workspace_root).strip():
        return {}

    skills_path = os.path.join(os.path.abspath(workspace_root), "skills.md")
    if not os.path.isfile(skills_path):
        logger.debug("No skills.md at workspace root: %s", skills_path)
        return {}

    try:
        with open(skills_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        logger.warning("Failed to read skills.md at %s: %s", skills_path, exc)
        return {}

    return parse_skills_md(content)


def languages_from_paths(paths: Iterable[str]) -> list[str]:
    """Derive display language names from file paths via extension mapping.

    Args:
        paths: Relative or absolute file paths (open editor tabs, etc.).

    Returns:
        Deduplicated list of language display names (e.g. ``["Python"]``).
    """
    seen: set[str] = set()
    languages: list[str] = []
    for path in paths or []:
        if not path:
            continue
        base = os.path.basename(path).lower()
        if base == "dockerfile":
            lang = "Docker"
        else:
            ext = os.path.splitext(path)[1].lower()
            lang = _EXT_TO_LANGUAGE.get(ext)
        if lang and lang not in seen:
            seen.add(lang)
            languages.append(lang)
    return languages


def _section_matches_language(section_name: str, language: str) -> bool:
    """Return True if a section name relates to a language label."""
    name_lower = section_name.lower()
    lang_lower = language.lower().strip()
    if not lang_lower:
        return False

    if lang_lower in name_lower or name_lower in lang_lower:
        return True

    aliases = _LANGUAGE_ALIASES.get(lang_lower, (lang_lower,))
    for alias in aliases:
        if alias in name_lower:
            return True
    # Also try alias map keyed by normalized language without punctuation.
    normalized = re.sub(r"[^a-z0-9+#.]", "", lang_lower)
    for key, alias_tuple in _LANGUAGE_ALIASES.items():
        if normalized == re.sub(r"[^a-z0-9+#.]", "", key) or normalized in alias_tuple:
            if any(a in name_lower for a in alias_tuple) or key in name_lower:
                return True
    return False


def select_relevant_sections(
    sections: dict[str, str],
    languages: list[str] | None,
    *,
    max_sections: int = _DEFAULT_MAX_SECTIONS,
) -> dict[str, str]:
    """Pick skills sections relevant to open-file languages.

    Always includes sections named like ``General`` or ``All`` (case-insensitive).
    When ``languages`` is empty, returns General/All plus remaining sections
    capped at ``max_sections``.

    Args:
        sections: Full parsed skills map.
        languages: Open file language labels (e.g. ``["Python", "TypeScript"]``).
        max_sections: Maximum number of sections to return when falling back
            to all sections or when many language matches exist.

    Returns:
        Ordered subset of ``sections`` to inject into a prompt.
    """
    if not sections:
        return {}

    languages = list(languages or [])
    selected: dict[str, str] = {}

    for name, body in sections.items():
        if name.lower().strip() in _ALWAYS_INCLUDE_NAMES:
            selected[name] = body

    if languages:
        for name, body in sections.items():
            if name in selected:
                continue
            if any(_section_matches_language(name, lang) for lang in languages):
                selected[name] = body
                if len(selected) >= max_sections:
                    break
        return selected

    # No open languages: General/All plus remaining sections, capped.
    for name, body in sections.items():
        if name in selected:
            continue
        selected[name] = body
        if len(selected) >= max_sections:
            break
    return selected


def format_skills_for_prompt(sections: dict[str, str]) -> str:
    """Format selected skills sections as a prompt-ready markdown block.

    Args:
        sections: Section name → body content to include.

    Returns:
        Formatted string, or empty string when ``sections`` is empty.
        Total length is capped to avoid blowing the system prompt budget.
    """
    if not sections:
        return ""

    parts: list[str] = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "WORKSPACE SKILLS (from skills.md)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for name, body in sections.items():
        parts.append(f"## {name}")
        parts.append(body.strip() if body else "")
        parts.append("")

    text = "\n".join(parts).rstrip() + "\n"
    if len(text) > _DEFAULT_MAX_CHARS:
        text = text[: _DEFAULT_MAX_CHARS - 20].rstrip() + "\n\n[...truncated...]\n"
    return text


def build_skills_prompt_section(
    workspace_root: str,
    languages: list[str] | None = None,
    open_files: list[str] | None = None,
) -> str:
    """Load workspace skills and format relevant sections for a system prompt.

    Args:
        workspace_root: Workspace directory containing optional ``skills.md``.
        languages: Optional explicit language labels from the editor.
        open_files: Optional open file paths used to infer languages when
            ``languages`` is not provided.

    Returns:
        Formatted skills block, or empty string when nothing applies.
    """
    sections = load_skills(workspace_root)
    if not sections:
        return ""

    effective_languages = list(languages or [])
    if not effective_languages and open_files:
        effective_languages = languages_from_paths(open_files)

    relevant = select_relevant_sections(sections, effective_languages)
    return format_skills_for_prompt(relevant)
