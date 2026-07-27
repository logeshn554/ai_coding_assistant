"""Tests for attachments.py — Multi-file attachment routing & prompt formatting."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.attachments import (
    AttachmentResult,
    format_attachment_prompt,
    is_image_file,
    process_attachments,
)
from app.vision import VisionResult


def test_is_image_file_extension_detection():
    """is_image_file correctly identifies image extensions."""
    assert is_image_file("diagram.png") is True
    assert is_image_file("photo.JPG") is True
    assert is_image_file("app.py") is False
    assert is_image_file("README.md") is False


@pytest.mark.asyncio
async def test_process_attachments_routing(tmp_path):
    """Images route to vision and code files route to RAG individually."""
    img_file = tmp_path / "mock_ui.png"
    img_file.write_bytes(b"fake image bytes")

    code_file = tmp_path / "utils.py"
    code_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    mock_vision_res = VisionResult(
        mode="vision_model",
        text="Detected navbar and sidebar buttons.",
        confidence=1.0,
    )

    with patch("app.attachments.analyze_image", new_callable=AsyncMock) as mock_vision:
        mock_vision.return_value = mock_vision_res
        results = await process_attachments(
            [str(img_file), str(code_file)],
            query="Explain helper functions",
            workspace_root=str(tmp_path),
        )

    assert len(results) == 2

    # Result 1: Image
    assert results[0].file_type == "image"
    assert results[0].mode == "vision_model"
    assert "navbar" in results[0].summary_or_chunks

    # Result 2: Code Document
    assert results[1].file_type == "document"
    assert results[1].mode == "rag"
    assert "add(a, b)" in results[1].summary_or_chunks


def test_format_attachment_prompt_headers():
    """format_attachment_prompt produces clear per-file headers."""
    items = [
        AttachmentResult(path="screen.png", file_type="image", summary_or_chunks="UI layout detected", mode="vision_model"),
        AttachmentResult(path="main.py", file_type="document", summary_or_chunks="def main(): pass", mode="rag"),
    ]

    prompt = format_attachment_prompt(items)
    assert "ATTACHED FILE CONTEXT" in prompt
    assert "### 📄 File: `screen.png` [IMAGE | Mode: vision_model]" in prompt
    assert "### 📄 File: `main.py` [DOCUMENT | Mode: rag]" in prompt
