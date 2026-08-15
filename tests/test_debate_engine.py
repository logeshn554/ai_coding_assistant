"""Unit tests for DebateEngine (LLM critic) — no hardcoded models."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.debate.debate_engine import DebateEngine, Critique, _extract_json
from backend.app.debate.consensus import ConsensusEngine


def test_extract_json_from_fenced_block():
    text = 'Here is my review:\n```json\n{"score": 8, "feedback": "ok", "blocking": false}\n```'
    parsed = _extract_json(text)
    assert parsed is not None
    assert parsed["score"] == 8


@pytest.mark.asyncio
async def test_hold_debate_skips_without_critic_profile():
    engine = DebateEngine(critic_profile=None)
    with patch("backend.app.debate.debate_engine._resolve_critic_profile", return_value=None):
        critiques = await engine.hold_debate("diff --git a/x b/x\n+print(1)")
    assert critiques == []


@pytest.mark.asyncio
async def test_hold_debate_uses_configured_profile_not_hardcoded_model():
    profile = {
        "model_name": "my-custom-critic",
        "api_key": "test-key",
        "api_format": "openai",
    }
    engine = DebateEngine(critic_profile=profile)

    async def fake_stream(*args, **kwargs):
        payload = {"score": 9, "feedback": "Looks good", "blocking": False, "issues": []}
        yield {"type": "text", "content": json.dumps(payload)}

    mock_adapter = MagicMock()
    mock_adapter.stream_chat = fake_stream
    mock_router = MagicMock()
    mock_router.get_adapter.return_value = mock_adapter

    with patch("backend.app.adapters.router.ModelRouter", return_value=mock_router):
        critiques = await engine.hold_debate("diff --git a/x b/x\n+print(1)")

    assert len(critiques) == 1
    assert critiques[0].score == 9
    assert critiques[0].is_blocking is False
    # Ensure the profile's model was passed through — never a hardcoded vendor id
    used_profile = mock_router.get_adapter.call_args[0][0]
    assert used_profile["model_name"] == "my-custom-critic"


def test_consensus_rejects_blocking():
    engine = ConsensusEngine()
    assert engine.resolve_consensus([]) is True
    assert engine.resolve_consensus([
        Critique(agent_name="c", score=9, feedback="ok"),
        Critique(agent_name="c2", score=3, feedback="bad", is_blocking=True),
    ]) is False
