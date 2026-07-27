"""Vision & OCR analysis service for DevPilot AI Assistant.

Provides `analyze_image(path)`:
1. If `image_analysis_model` setting is set, dispatches to vision-capable model.
2. If unset or unreachable, falls back to OCR via `pytesseract` + `Pillow` (or PIL image summary).
Logs which path (vision_model vs ocr) was executed.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .state import config_manager

logger = logging.getLogger("devpilot.vision")


@dataclass
class VisionResult:
    """Structured result of image analysis."""

    mode: str  # "vision_model" or "ocr"
    text: str
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_ocr_fallback(path: str) -> VisionResult:
    """Extract text from an image using pytesseract or Pillow summary."""
    try:
        from PIL import Image
    except ImportError as err:
        logger.warning("PIL / Pillow not installed: %s", err)
        return VisionResult(
            mode="ocr",
            text=f"[Image File: {os.path.basename(path)} (Pillow not installed)]",
            confidence=0.0,
        )

    try:
        with Image.open(path) as img:
            format_name = img.format or "UNKNOWN"
            width, height = img.size
            mode = img.mode

            # Try pytesseract OCR extraction
            extracted_text = ""
            try:
                import pytesseract
                extracted_text = pytesseract.image_to_string(img).strip()
            except Exception as ocr_err:
                logger.debug("Pytesseract OCR failed or binary not found: %s", ocr_err)

            if extracted_text:
                logger.info("Vision: Used OCR (pytesseract) for '%s'", path)
                return VisionResult(
                    mode="ocr",
                    text=f"[OCR Extracted Text from {os.path.basename(path)}]\n{extracted_text}",
                    confidence=0.85,
                )

            # Pillow image properties summary fallback
            logger.info("Vision: Used OCR (Pillow summary) for '%s'", path)
            return VisionResult(
                mode="ocr",
                text=(
                    f"[Image Summary: {os.path.basename(path)}]\n"
                    f"Format: {format_name}, Size: {width}x{height}px, Color Mode: {mode}"
                ),
                confidence=0.6,
            )
    except Exception as exc:
        logger.error("Failed to open image for OCR '%s': %s", path, exc)
        return VisionResult(
            mode="ocr",
            text=f"[Image File: {os.path.basename(path)} (Unreadable image file)]",
            confidence=0.0,
        )


async def analyze_image(path: str) -> VisionResult:
    """Analyze an image file using configured vision_model or OCR fallback.

    Args:
        path: Absolute or workspace-relative path to image file.

    Returns:
        VisionResult containing mode ("vision_model" or "ocr"), text, and confidence.
    """
    if not path or not os.path.exists(path):
        return VisionResult(
            mode="ocr",
            text=f"[Image File Not Found: {path}]",
            confidence=0.0,
        )

    vision_model = config_manager.get_image_analysis_model().strip()

    if vision_model:
        try:
            from .adapters.router import ModelRouter
            router = ModelRouter()
            profile = config_manager.get_active_profile()
            profile_to_use = dict(profile)
            profile_to_use["model_name"] = vision_model

            with open(path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            ext = os.path.splitext(path)[1].lower().lstrip(".")
            mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
            data_uri = f"data:{mime};base64,{b64_data}"

            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Describe this image ({os.path.basename(path)}). "
                        f"Analyze UI layout, text content, and visual components.\n\n"
                        f"[ATTACHMENT_IMAGE: {data_uri[:100]}...]"
                    ),
                }
            ]

            result_text = await router.completion(
                profile=profile_to_use,
                messages=messages,
                system_prompt="You are a vision-capable AI visual inspector.",
            )

            if result_text and result_text.strip():
                logger.info("Vision: Used vision_model '%s' for '%s'", vision_model, path)
                return VisionResult(
                    mode="vision_model",
                    text=f"[Vision Model Analysis: {vision_model}]\n{result_text.strip()}",
                    confidence=1.0,
                )
        except Exception as exc:
            logger.warning("Vision model '%s' failed for '%s': %s. Falling back to OCR.", vision_model, path, exc)

    # Fallback to OCR path
    return _extract_ocr_fallback(path)
