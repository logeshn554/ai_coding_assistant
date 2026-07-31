"""Tests for skills discoverability — Feature 2.

Covers:
- Python/FastAPI task_description matches relevant sections, respects limits.
- Unrelated task_description does NOT pull in the full section body.
- /api/skills/match endpoint returns matched sections and inferred languages.
- select_relevant_sections discriminates between two different skills files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# Shared sample skills.md content used by all tests.
# ---------------------------------------------------------------------------
_SAMPLE_SKILLS_MD = """\
## Python Best Practices
Use type hints. Follow PEP 8. Write docstrings for every public function.

## FastAPI Patterns
Use Pydantic v2 models. Prefer dependency injection via Depends(). Write async endpoints.

## Security
Never store secrets in source code. Use parameterized queries. Rate-limit all public endpoints.

## JavaScript Tips
Prefer const over let. Use async/await. Avoid global state.

## General
Write tests for every new function. Keep functions under 30 lines.
"""

_REVIEWER_SKILLS_MD = """\
## Review Structure
List findings by severity: Critical, High, Medium, Low.

## Security Review
Scan for SQL injection, hardcoded tokens, missing auth checks.

## General
Provide a "What's done well" section at the end.
"""


# ===========================================================================
# 1 — parse_skills_md round-trip
# ===========================================================================
def test_parse_skills_md_sections():
    """parse_skills_md correctly extracts all ## sections."""
    from app.skills_loader import parse_skills_md

    sections = parse_skills_md(_SAMPLE_SKILLS_MD)
    assert "Python Best Practices" in sections
    assert "FastAPI Patterns" in sections
    assert "Security" in sections
    assert "JavaScript Tips" in sections
    assert "General" in sections
    assert "Use type hints" in sections["Python Best Practices"]


# ===========================================================================
# 2 — Python/FastAPI task matches relevant sections
# ===========================================================================
def test_python_task_matches_python_sections(tmp_path):
    """A Python/FastAPI task description pulls in Python-relevant sections."""
    from app.skills_loader import (
        parse_skills_md,
        select_relevant_sections,
        _DEFAULT_MAX_SECTIONS,
    )

    sections = parse_skills_md(_SAMPLE_SKILLS_MD)
    task = "Implement a FastAPI endpoint with Python type hints and Pydantic validation."
    desc_lower = task.lower()

    # Replicate the language-inference logic used by SkillsLoader.load_for_task.
    from app.skills_loader import _LANGUAGE_ALIASES
    inferred: list[str] = []
    for lang_key, aliases in _LANGUAGE_ALIASES.items():
        keywords = (lang_key,) + (aliases if isinstance(aliases, tuple) else (aliases,))
        if any(kw in desc_lower for kw in keywords):
            inferred.append(lang_key.capitalize())

    matched = select_relevant_sections(sections, inferred)

    # Must include Python-related section(s).
    assert any("python" in k.lower() or "fastapi" in k.lower() for k in matched), (
        f"Expected Python/FastAPI section in matched keys: {list(matched.keys())}"
    )
    # Must not exceed the default cap.
    assert len(matched) <= _DEFAULT_MAX_SECTIONS


# ===========================================================================
# 3 — Unrelated task does NOT pull in language-specific sections for a
#     language that has no matching sections in the skills file.
# ===========================================================================
def test_unrelated_task_does_not_pull_extra_sections(tmp_path):
    """A Go task on a Python/JS skills file returns only the General section.

    The sample skills file has Python, FastAPI, Security, JavaScript, and General
    sections.  A Go task should only match General (always-include) because there
    is no Go section in the file.  This verifies that select_relevant_sections
    does NOT fall back to returning *all* sections when a language is matched but
    no section name relates to it.
    """
    from app.skills_loader import parse_skills_md, select_relevant_sections

    sections = parse_skills_md(_SAMPLE_SKILLS_MD)

    # Explicitly pass ["Go"] as the language — no Go section exists in the sample.
    matched = select_relevant_sections(sections, ["Go"])

    # Only "General" (always-include) should appear; Python-specific should be absent.
    assert "Python Best Practices" not in matched, (
        "Python Best Practices should not appear for a Go-only task."
    )
    assert "FastAPI Patterns" not in matched, (
        "FastAPI Patterns should not appear for a Go-only task."
    )
    # General must still be present (always-include rule).
    assert "General" in matched, "General section should always be included."


# ===========================================================================
# 5 — /api/skills/match endpoint returns matched sections and languages
# ===========================================================================

def test_skills_match_endpoint_python_task(tmp_path):
    """GET /api/skills/match?task=... returns matched sections for python tasks."""
    from unittest.mock import patch
    from app.main import app

    client = TestClient(app)

    with patch("app.routes.skills.load_skills", return_value={"Python Best Practices": "Use type hints.", "General": "Write tests."}):
        with patch("app.state.workspace_state") as mock_ws:
            mock_ws.root = str(tmp_path)
            response = client.get("/api/skills/match", params={"task": "write a python function"})

    assert response.status_code == 200
    data = response.json()
    assert "sections" in data
    assert "formatted" in data
    assert "inferred_languages" in data
    assert isinstance(data["sections"], dict)
    assert isinstance(data["inferred_languages"], list)


def test_skills_match_endpoint_returns_empty_without_skills_md(tmp_path):
    """GET /api/skills/match returns empty sections when skills.md is absent."""
    from unittest.mock import patch
    from app.main import app

    client = TestClient(app)

    with patch("app.routes.skills.load_skills", return_value={}):
        with patch("app.state.workspace_state") as mock_ws:
            mock_ws.root = str(tmp_path)
            response = client.get("/api/skills/match", params={"task": "anything"})

    assert response.status_code == 200
    data = response.json()
    assert data["sections"] == {}
    assert data["formatted"] == ""


def test_skills_match_endpoint_missing_task_param():
    """GET /api/skills/match without ?task= returns 422 (required query param)."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/skills/match")
    assert response.status_code == 422  # FastAPI validation error


# ===========================================================================
# 6 — Two different skills files score differently on the same task
# ===========================================================================
def test_two_skills_discriminate():
    """elite_coder and code_reviewer sections score differently for the same task."""
    from app.skills_loader import parse_skills_md, select_relevant_sections, _LANGUAGE_ALIASES

    elite_sections = parse_skills_md(_SAMPLE_SKILLS_MD)
    reviewer_sections = parse_skills_md(_REVIEWER_SKILLS_MD)

    # A "review" task.
    task = "Please review this Python code for security issues."
    desc_lower = task.lower()
    inferred: list[str] = []
    for lang_key, aliases in _LANGUAGE_ALIASES.items():
        keywords = (lang_key,) + (aliases if isinstance(aliases, tuple) else (aliases,))
        if any(kw in desc_lower for kw in keywords):
            inferred.append(lang_key.capitalize())

    elite_matched = select_relevant_sections(elite_sections, inferred)
    reviewer_matched = select_relevant_sections(reviewer_sections, inferred)

    # The two matched sets must differ — they represent different skills.
    elite_keys = set(elite_matched.keys())
    reviewer_keys = set(reviewer_matched.keys())
    assert elite_keys != reviewer_keys, (
        "Expected elite_coder and code_reviewer to score differently for the same task."
    )


# ===========================================================================
# 7 — format_skills_for_prompt truncates at _DEFAULT_MAX_CHARS
# ===========================================================================
def test_format_skills_truncates_at_max_chars():
    """format_skills_for_prompt truncates output when sections exceed _DEFAULT_MAX_CHARS."""
    from app.skills_loader import format_skills_for_prompt, _DEFAULT_MAX_CHARS

    # Build a section that is definitely larger than the char limit.
    huge_body = "x" * (_DEFAULT_MAX_CHARS + 5000)
    sections = {"Huge Section": huge_body}
    result = format_skills_for_prompt(sections)

    assert len(result) <= _DEFAULT_MAX_CHARS + 50, (
        f"Output ({len(result)} chars) exceeds _DEFAULT_MAX_CHARS ({_DEFAULT_MAX_CHARS})"
    )
    assert "[...truncated...]" in result
