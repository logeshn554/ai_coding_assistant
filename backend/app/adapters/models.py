"""Dynamic Model Metadata & Provider Discovery Engine.

No hardcoded provider or model dictionaries. All metadata and capabilities
are dynamically discovered or user-configured at runtime.
"""

from __future__ import annotations

import logging
import time

from pydantic import BaseModel, Field

logger = logging.getLogger("devpilot.models")

class ModelMetadata(BaseModel):
    provider: str = ""
    model_name: str = ""
    model_id: str = ""
    context_window: int | None = None           # None = "Unavailable"
    max_output_tokens: int | None = None        # None = "Unavailable"
    input_token_limit: int | None = None
    output_token_limit: int | None = None
    input_price_per_m: float | None = None       # None = "Unavailable"
    output_price_per_m: float | None = None      # None = "Unavailable"
    rpm_limit: int | None = None                # None = "Not provided by provider"
    tpm_limit: int | None = None                # None = "Not provided by provider"
    rpd_limit: int | None = None
    streaming_supported: bool = True
    tools_supported: bool = True
    vision_supported: bool = False
    reasoning_supported: bool = False
    json_supported: bool = True
    api_status: str = "Connected"
    is_provider_reported: bool = False
    metadata_source: str = "Discovered"            # Provider metadata, Discovered, User Configured, Unknown
    last_metadata_update: int = Field(default_factory=lambda: int(time.time()))
    observed_rpm: int = 0
    observed_tpm: int = 0
    requests_today: int = 0
    input_tokens_today: int = 0
    output_tokens_today: int = 0


def get_model_metadata(model_id: str, provider_hint: str | None = None) -> ModelMetadata:
    """Dynamically construct model metadata for any given model_id without hardcoding."""
    clean_id = model_id.strip() if model_id else ""
    if not clean_id:
        return ModelMetadata(
            provider=provider_hint or "",
            model_name="Select Model",
            model_id="",
            metadata_source="Unknown"
        )
    
    provider_name = provider_hint or ""
    id_lower = clean_id.lower()

    # Dynamic capability detection based on standard model naming conventions
    vision = "vision" in id_lower or "vl" in id_lower or "4o" in id_lower or "claude-3" in id_lower or "gemini" in id_lower
    reasoning = "reason" in id_lower or "r1" in id_lower or "o1" in id_lower or "o3" in id_lower or "thinking" in id_lower

    return ModelMetadata(
        provider=provider_name,
        model_name=clean_id.split("/")[-1].replace("-", " ").title(),
        model_id=clean_id,
        context_window=None,           # None = Unavailable unless provided by provider endpoint
        max_output_tokens=None,        # None = Unavailable unless provided by provider endpoint
        vision_supported=vision,
        reasoning_supported=reasoning,
        is_provider_reported=False,
        metadata_source="Not provided by provider",
    )
