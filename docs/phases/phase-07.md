# Phase 7: Model Router

## Goal
Enforce model selections, exponential backoff retries, rate limits, and fallback routines.

## Achievements
*   Implemented `ModelRouter` in `agent_os/providers/model_router.py`.
*   Supported capability mappings matching keywords (Claude, GPT, Gemini, Groq, Ollama) to target providers.
*   Enforced slide-window Requests Per Minute (RPM) limits.
*   Implemented exponential backoff retries and dynamic unhealthy fallback provider switching.

## Verification
*   `test_model_router.py`
