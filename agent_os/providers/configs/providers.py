"""
Provider Config Presets — Predefined protocols and settings for different LLM endpoints.
"""

from __future__ import annotations

from typing import Dict
from agent_os.providers.base import ProviderConfig

PROVIDER_PRESETS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        protocol="openai",
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        model="claude-3-5-sonnet",
        base_url="https://api.anthropic.com/v1",
        protocol="anthropic",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        model="gemini-1.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        protocol="openai",  # Gemini supports OpenAI-compatibility endpoint
    ),
    "groq": ProviderConfig(
        name="groq",
        model="llama3-70b-8192",
        base_url="https://api.groq.com/openai/v1",
        protocol="openai",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        model="meta-llama/llama-3-70b-instruct",
        base_url="https://openrouter.ai/api/v1",
        protocol="openai",
    ),
    "ollama": ProviderConfig(
        name="ollama",
        model="llama3",
        base_url="http://localhost:11434/v1",
        protocol="openai",
    ),
}
