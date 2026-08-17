"""
Self Evolving Prompts — Adjusts prompt structures based on historical success rates.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("loopix.repair.self_evolving_prompts")


class SelfEvolvingPrompts:
    """Modifies agent system instructions dynamically to avoid repeating past mistakes."""

    def __init__(self) -> None:
        self._modifications: dict[str, str] = {
            "code": "Focus on complete code syntax. Do not write placeholders or empty functions.",
            "test": "Verify boundary conditions and mock network calls explicitly.",
            "review": "Enforce naming style conventions and structural code contracts strictly.",
        }

    def get_optimized_instruction(self, agent_type: str) -> str:
        """Retrieve instruction suffix optimized for the given agent category."""
        return self._modifications.get(agent_type, "")

    def evolve_instruction(self, agent_type: str, failure_reason: str) -> None:
        """Evolve instruction based on failure context."""
        existing = self._modifications.get(agent_type, "")
        if "syntax" in failure_reason.lower() or "parsing" in failure_reason.lower():
            self._modifications[agent_type] = f"{existing} Ensure correct syntax indentation."
        elif "contract" in failure_reason.lower() or "violation" in failure_reason.lower():
            self._modifications[agent_type] = f"{existing} Match interface signatures strictly."
        
        logger.info(f"Evolved instructions for '{agent_type}': {self._modifications[agent_type][:80]}...")


# ── Singleton ───────────────────────────────────────────────────────────────

self_evolving_prompts = SelfEvolvingPrompts()
