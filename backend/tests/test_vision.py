"""Tests for vision.py — Image Analysis and OCR Fallback."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.vision import VisionResult, analyze_image


@pytest.mark.asyncio
async def test_analyze_image_vision_model_path(tmp_path):
    """When image_analysis_model is configured, analyze_image dispatches to vision model."""
    test_img = tmp_path / "test_screen.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01")

    with patch("app.state.config_manager.get_image_analysis_model", return_value="gpt-4o"):
        with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = "Detected login button at (100, 200) and user avatar."
            result: VisionResult = await analyze_image(str(test_img))

    assert result.mode == "vision_model"
    assert "login button" in result.text
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_analyze_image_ocr_fallback(tmp_path):
    """When no vision model is configured, analyze_image falls through to OCR."""
    test_img = tmp_path / "doc_scan.png"
    test_img.write_bytes(b"fake image content")

    with patch("app.state.config_manager.get_image_analysis_model", return_value=""):
        result: VisionResult = await analyze_image(str(test_img))

    assert result.mode == "ocr"
    assert len(result.text) > 0
    assert result.confidence < 1.0


@pytest.mark.asyncio
async def test_analyze_image_nonexistent_file():
    """analyze_image returns confidence 0 for missing file."""
    result: VisionResult = await analyze_image("/nonexistent/file.png")
    assert result.mode == "ocr"
    assert "Not Found" in result.text
    assert result.confidence == 0.0
