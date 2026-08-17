"""
Debate Engine — Invokes a configured critic LLM to review proposed diffs.

Uses the ModelRouter + critic profile from settings/config. No hardcoded model IDs.
When no critic profile is configured, debates are skipped (empty critique list).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("loopix.debate.debate_engine")

CRITIC_SYSTEM = """You are a senior code reviewer.
Analyse the given unified diff and respond ONLY with JSON:
{"score": 1-10, "feedback": "...", "blocking": true/false,
 "issues": [{"type": "security|perf|correctness", "line": N, "desc": "..."}]}
Score 1-4 = blocking problems, 5-7 = warnings, 8-10 = approved."""


@dataclass
class Critique:
    """Single peer-review verdict from a critic agent."""

    agent_name: str
    score: int  # 1 to 10
    feedback: str
    is_blocking: bool = False
    issues: list[dict[str, Any]] = field(default_factory=list)


def _resolve_critic_profile(explicit: dict | None = None) -> dict | None:
    """Build critic profile from explicit arg, settings, or named config profile.

    Never invents a model name — returns None when critic is not configured.
    """
    if explicit and explicit.get("model_name"):
        return dict(explicit)

    try:
        from ..config import config_manager, settings
    except Exception:
        return None

    profile_id = (getattr(settings, "CRITIC_MODEL_PROFILE", "") or "").strip()
    if not profile_id:
        return None

    # Prefer a saved profile by id/name so model/api_key come from user config
    try:
        saved = config_manager.get_profile(profile_id)
        if saved and saved.get("model_name"):
            return saved
        listed = config_manager.list_profiles(mask_keys=False) or {}
        for p in listed.get("profiles") or []:
            if p.get("id") == profile_id or p.get("name") == profile_id:
                if p.get("model_name"):
                    return p
    except Exception as exc:
        logger.debug("Critic profile lookup failed: %s", exc)

    # Fallback: treat CRITIC_MODEL_PROFILE as a model name only if API key provided
    api_key = (
        getattr(settings, "CRITIC_API_KEY", "")
        or getattr(settings, "ANTHROPIC_API_KEY", "")
        or getattr(settings, "OPENAI_API_KEY", "")
        or ""
    ).strip()
    if not api_key:
        logger.warning(
            "CRITIC_MODEL_PROFILE is set but no API key available; skipping debate."
        )
        return None

    api_format = (getattr(settings, "CRITIC_API_FORMAT", "") or "").strip() or "openai"
    return {
        "model_name": profile_id,
        "api_key": api_key,
        "api_format": api_format,
        "base_url": getattr(settings, "CRITIC_BASE_URL", "") or "",
    }


def _extract_json(text: str) -> dict | None:
    """Parse JSON from model output, tolerating fenced markdown wrappers."""
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except Exception:
            pass
    brace = re.search(r"\{[\s\S]*\}", raw)
    if brace:
        try:
            return json.loads(brace.group(0))
        except Exception:
            pass
    return None


class DebateEngine:
    """Invokes a configured critic LLM prior to merge / verification acceptance."""

    def __init__(self, critic_profile: dict | None = None) -> None:
        self.critic_profile = critic_profile

    async def hold_debate(self, patch_diff: str) -> list[Critique]:
        """Gather critique reports from the configured critic model.

        Returns an empty list when no critic is configured or the response is
        malformed — never blocks the agent on critic infrastructure failures.
        """
        if not patch_diff or not str(patch_diff).strip():
            return []

        profile = _resolve_critic_profile(self.critic_profile)
        if not profile:
            return []

        try:
            from ..adapters.router import ModelRouter

            router = ModelRouter()
            adapter = router.get_adapter(profile, is_agent=False, task_type="review")
        except Exception as exc:
            logger.warning("DebateEngine: failed to resolve critic adapter: %s", exc)
            return []

        response_text = ""
        messages = [
            {
                "role": "user",
                "content": f"Review this diff:\n```diff\n{patch_diff[:6000]}\n```",
            }
        ]

        try:
            async for chunk in adapter.stream_chat(
                messages, tools=[], system_prompt=CRITIC_SYSTEM
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    response_text += chunk.get("content") or ""
        except Exception as exc:
            logger.warning("DebateEngine: critic stream failed: %s", exc)
            return []

        parsed = _extract_json(response_text)
        if not parsed:
            logger.info("DebateEngine: critic returned non-JSON; skipping.")
            return []

        try:
            score = int(parsed.get("score", 7))
        except (TypeError, ValueError):
            score = 7
        score = max(1, min(10, score))

        blocking = bool(parsed.get("blocking", score <= 4))
        issues = parsed.get("issues") if isinstance(parsed.get("issues"), list) else []

        critique = Critique(
            agent_name="llm_critic",
            score=score,
            feedback=str(parsed.get("feedback") or ""),
            is_blocking=blocking,
            issues=issues,
        )
        logger.info(
            "Debate completed: score=%s blocking=%s", critique.score, critique.is_blocking
        )
        return [critique]


# ── Singleton (profile resolved lazily on each hold_debate call) ──────────────

debate_engine = DebateEngine()
