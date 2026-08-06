"""
Consensus Engine — Aggregates peer critiques and calculates a single decision score.
"""
from __future__ import annotations

import logging
from typing import List
from .debate_engine import Critique

logger = logging.getLogger("devpilot.debate.consensus")


class ConsensusEngine:
    """Combines peer critique scores to decide whether to merge, revise, or reject changes."""

    def resolve_consensus(self, critiques: List[Critique]) -> bool:
        """Resolve agreement based on critique scores and blocking flags.

        Returns True if approved, False if rejected.
        """
        if not critiques:
            return True

        # If any agent logs a blocking critique, consensus immediately fails
        if any(c.is_blocking for c in critiques):
            logger.warning("Consensus rejected: A blocking critique was logged.")
            return False

        # Calculate average score
        total_score = sum(c.score for c in critiques)
        avg = total_score / len(critiques)
        
        # Approve if average is at least 6.5
        approved = (avg >= 6.5)
        if approved:
            logger.info(f"Consensus approved: average score = {avg:.2f}")
        else:
            logger.warning(f"Consensus rejected: average score {avg:.2f} is below threshold")

        return approved


# ── Singleton ───────────────────────────────────────────────────────────────

consensus_engine = ConsensusEngine()
