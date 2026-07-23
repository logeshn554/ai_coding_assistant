"""AI inline completions endpoint for Monaco ghost-text suggestions."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..state import config_manager

logger = logging.getLogger("devpilot.completions")

router = APIRouter()


class CompletionRequest(BaseModel):
    """Request body for POST /api/completions."""

    prefix: str = Field(..., description="Code before the cursor")
    suffix: str = Field("", description="Code after the cursor (for FIM models)")
    language: str = Field("", description="Language identifier, e.g. 'python'")
    file_path: str = Field("", description="Relative file path for context")
    max_tokens: int = Field(128, ge=1, le=512)


class CompletionResponse(BaseModel):
    """Response body for POST /api/completions."""

    completion: str
    model: str


_SYSTEM_PROMPT = (
    "You are an expert inline code completion engine. "
    "Complete the code at the cursor without explanation, markdown fences, or preamble. "
    "Output ONLY the completion text — nothing else."
)


@router.post("/api/completions", response_model=CompletionResponse)
async def create_completion(req: CompletionRequest) -> CompletionResponse:
    """Return a single inline code completion for the given prefix/suffix.

    Falls back to an empty completion rather than raising 500 on any model error,
    so the editor ghost-text is silently suppressed instead of showing an error toast.
    """
    profile = config_manager.get_active_profile()
    provider: str = (profile.get("provider") or "anthropic").lower()
    model: str = profile.get("model") or "claude-opus-4-5"
    api_key: Optional[str] = profile.get("api_key") or None

    # Build a tight fill-in-the-middle style prompt
    lang_hint = f"Language: {req.language}\n" if req.language else ""
    path_hint = f"File: {req.file_path}\n" if req.file_path else ""
    user_content = (
        f"{lang_hint}{path_hint}"
        f"<prefix>{req.prefix}</prefix>"
        f"<suffix>{req.suffix}</suffix>"
        "\nComplete the code at the cursor:"
    )

    try:
        completion_text = await _call_model(
            provider=provider,
            model=model,
            api_key=api_key,
            system=_SYSTEM_PROMPT,
            user=user_content,
            max_tokens=req.max_tokens,
        )
        return CompletionResponse(completion=completion_text, model=model)

    except Exception as exc:
        logger.warning("Completion request failed (%s): %s", provider, exc)
        # Return empty — the frontend hides ghost text if completion is empty
        return CompletionResponse(completion="", model=model)


async def _call_model(
    *,
    provider: str,
    model: str,
    api_key: Optional[str],
    system: str,
    user: str,
    max_tokens: int,
) -> str:
    """Dispatch to the configured LLM provider and return the text completion."""

    if provider in ("anthropic", "claude"):
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        blocks = response.content or []
        return "".join(
            b.text for b in blocks if hasattr(b, "text")
        )

    if provider in ("openai", "gpt"):
        import openai

        client = openai.AsyncOpenAI(api_key=api_key) if api_key else openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    if provider == "ollama":
        import httpx

        base_url = profile_base_url(provider) or "http://localhost:11434"
        payload = {
            "model": model,
            "prompt": f"{system}\n{user}",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(f"{base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return (resp.json().get("response") or "").strip()

    raise HTTPException(status_code=400, detail=f"Unsupported provider for completions: {provider}")


def profile_base_url(provider: str) -> Optional[str]:
    """Extract a custom base_url from the active profile, if set."""
    try:
        profile = config_manager.get_active_profile()
        return profile.get("base_url") or None
    except Exception:
        return None
