"""
Provider Config Presets — Predefined protocols and settings for different LLM endpoints.

Model names are resolved from environment variables first so that no hardcoded model ID
is forced at runtime.  Set the corresponding env var in your .env file to override:

  DEVPILOT_OPENAI_MODEL=gpt-4o
  DEVPILOT_ANTHROPIC_MODEL=claude-sonnet-4-5
  DEVPILOT_GEMINI_MODEL=gemini-2.0-flash
  DEVPILOT_GROQ_MODEL=llama3-70b-8192
  DEVPILOT_OPENROUTER_MODEL=meta-llama/llama-3-70b-instruct
  DEVPILOT_OLLAMA_MODEL=llama3
"""

from __future__ import annotations

import os
from typing import Dict
from agent_os.providers.base import ProviderConfig

PROVIDER_PRESETS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        model=os.environ.get("DEVPILOT_OPENAI_MODEL", "gpt-4o-mini"),
        base_url="https://api.openai.com/v1",
        protocol="openai",
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        model=os.environ.get("DEVPILOT_ANTHROPIC_MODEL", "claude-3-5-sonnet"),
        base_url="https://api.anthropic.com/v1",
        protocol="anthropic",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        model=os.environ.get("DEVPILOT_GEMINI_MODEL", "gemini-1.5-flash"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        protocol="openai",  # Gemini supports OpenAI-compatibility endpoint
    ),
    "groq": ProviderConfig(
        name="groq",
        model=os.environ.get("DEVPILOT_GROQ_MODEL", "llama3-70b-8192"),
        base_url="https://api.groq.com/openai/v1",
        protocol="openai",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        model=os.environ.get("DEVPILOT_OPENROUTER_MODEL", "meta-llama/llama-3-70b-instruct"),
        base_url="https://openrouter.ai/api/v1",
        protocol="openai",
    ),
    "ollama": ProviderConfig(
        name="ollama",
        model=os.environ.get("DEVPILOT_OLLAMA_MODEL", "llama3"),
        base_url="http://localhost:11434/v1",
        protocol="openai",
    ),
}
