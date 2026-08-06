"""
Debate Engine — Invokes peer reviews where multiple agent viewpoints critique proposed changes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger("devpilot.debate.debate_engine")


@dataclass
class Critique:
    agent_name: str
    score: int                          # 1 to 10
    feedback: str
    is_blocking: bool = False


class DebateEngine:
    """Invokes specialist reviews prior to code merge checks."""

    def hold_debate(self, patch_diff: str) -> List[Critique]:
        """Gather critique reports from virtual review agents (e.g. security advisor, performance critic)."""
        critiques = []

        # 1. Security check heuristic
        if "eval(" in patch_diff or "exec(" in patch_diff:
            critiques.append(
                Critique(
                    agent_name="security_critic",
                    score=3,
                    feedback="Security risk: Found unsafe execution statement (eval/exec).",
                    is_blocking=True
                )
            )
        else:
            critiques.append(
                Critique(
                    agent_name="security_critic",
                    score=9,
                    feedback="No obvious vulnerabilities detected in modifications."
                )
            )

        # 2. Performance check heuristic
        if "while True:" in patch_diff or ".sleep(" in patch_diff:
            critiques.append(
                Critique(
                    agent_name="performance_critic",
                    score=6,
                    feedback="Performance warning: Check infinite loop risks or blockages."
                )
            )
        else:
            critiques.append(
                Critique(
                    agent_name="performance_critic",
                    score=10,
                    feedback="No performance bottlenecks identified."
                )
            )

        logger.info(f"Debate completed: gathered {len(critiques)} agent critiques.")
        return critiques


# ── Singleton ───────────────────────────────────────────────────────────────

debate_engine = DebateEngine()
