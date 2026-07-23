"""Unit tests for session history persistence and API helpers."""

from __future__ import annotations

import json

import pytest

from backend.app.db import first_user_preview, truncate_preview


def test_truncate_preview_short() -> None:
    assert truncate_preview("hello", 60) == "hello"


def test_truncate_preview_long() -> None:
    text = "a" * 80
    result = truncate_preview(text, 60)
    assert len(result) == 60
    assert result.endswith("…")


def test_first_user_preview_finds_user() -> None:
    messages = [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "Please fix the login form validation logic now"},
    ]
    preview = first_user_preview(messages, 60)
    assert preview.startswith("Please fix")
    assert len(preview) <= 60


def test_first_user_preview_empty() -> None:
    assert first_user_preview([], 60) == "(no messages)"


def test_first_user_preview_dict_content() -> None:
    messages = [{"role": "user", "content": {"text": "x"}}]
    preview = first_user_preview(messages, 60)
    assert "text" in preview
