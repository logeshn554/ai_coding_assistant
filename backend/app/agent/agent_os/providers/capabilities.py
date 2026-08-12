"""
Model Capabilities — Defines capabilities supported by different models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelCapabilities:
    """Represents capabilities and token limits of a specific model."""
    streaming: bool
    tool_calling: bool
    structured_output: bool
    vision: bool
    reasoning: bool
    max_context_tokens: int


def get_model_capabilities(model_name: str) -> ModelCapabilities:
    """Retrieve capabilities for a given model name dynamically."""
    if not model_name:
        return ModelCapabilities(
            streaming=True, tool_calling=True, structured_output=True, vision=False, reasoning=False, max_context_tokens=0
        )
    
    id_l = model_name.lower()
    vision = "vision" in id_l or "vl" in id_l or "4o" in id_l or "claude-3" in id_l or "gemini" in id_l
    reasoning = "reason" in id_l or "r1" in id_l or "o1" in id_l or "o3" in id_l or "thinking" in id_l

    return ModelCapabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=vision,
        reasoning=reasoning,
        max_context_tokens=0  # 0 = Not hardcoded, retrieved from provider
    )
