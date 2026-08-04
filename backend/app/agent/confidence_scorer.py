"""Phase 7 — Confidence Scorer.

Scores how confident the agent should be about a decision.
Low confidence → collect more context before acting.
Very low confidence → ask the user.

Scoring factors:
  - Are all referenced files resolved?
  - Is the tech stack known?
  - Is the request unambiguous?
  - Are all symbols found?
  - Is the workspace non-empty?
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .intent_router import IntentType

logger = logging.getLogger("devpilot.agent.confidence_scorer")

# Confidence thresholds
THRESHOLD_AUTO_PROCEED = 0.75      # ≥ this → proceed autonomously
THRESHOLD_COLLECT_MORE = 0.50      # ≥ this, < proceed → collect more context
THRESHOLD_ASK_USER = 0.50          # < this → ask user for clarification


@dataclass
class ConfidenceResult:
    score: float                    # 0.0 – 1.0
    action: str                     # "proceed", "collect_more", "ask_user"
    reasons: list[str]              # Factors that lowered confidence
    missing: list[str]              # Specific missing information


class ConfidenceScorer:
    """Score agent confidence before execution.

    Usage:
        scorer = ConfidenceScorer()
        result = scorer.score(intent, referenced_files, resolved_files, ...)
        if result.action == "ask_user":
            # surface a question
        elif result.action == "collect_more":
            # run context collector
    """

    def score(
        self,
        intent: IntentType,
        referenced_files: list[str],
        resolved_files: list[str],   # Files that were actually found and read
        tech_stack_known: bool,
        spec_file_read: bool,
        workspace_non_empty: bool,
        query_length: int,
        symbols_found: dict[str, str],
        referenced_symbols: list[str],
    ) -> ConfidenceResult:
        """Score the agent's confidence for proceeding with the current task.

        Args:
            intent: The classified intent type.
            referenced_files: Files mentioned in the user query.
            resolved_files: Files that were actually located and read.
            tech_stack_known: Whether the tech stack could be detected from manifests.
            spec_file_read: Whether a spec file was found and read.
            workspace_non_empty: Whether the workspace contains files.
            query_length: Character length of the user's request.
            symbols_found: Symbols found in the knowledge store {name → location}.
            referenced_symbols: Symbol names mentioned in the query.

        Returns:
            ConfidenceResult with score, action, and reasons.
        """
        score = 1.0
        reasons = []
        missing = []

        # ── Factor 1: Unresolved file references ─────────────────────────
        unresolved = [f for f in referenced_files if f not in resolved_files]
        if unresolved:
            penalty = min(len(unresolved) * 0.15, 0.45)
            score -= penalty
            reasons.append(f"{len(unresolved)} referenced file(s) not found: {unresolved[:3]}")
            missing.extend(unresolved[:3])

        # ── Factor 2: IMPLEMENT_SPEC without spec ────────────────────────
        if intent == IntentType.IMPLEMENT_SPEC and not spec_file_read:
            score -= 0.30
            reasons.append("IMPLEMENT_SPEC intent but no spec file was found/read.")
            missing.append("spec file (*.md, *.txt)")

        # ── Factor 3: Tech stack unknown for project-level tasks ─────────
        if not tech_stack_known and intent in (
            IntentType.NEW_PROJECT, IntentType.IMPLEMENT_SPEC, IntentType.REFACTOR
        ):
            score -= 0.15
            reasons.append("Tech stack could not be determined from manifest files.")
            missing.append("package.json / requirements.txt / go.mod")

        # ── Factor 4: Empty workspace for non-trivial tasks ──────────────
        if not workspace_non_empty and intent not in (
            IntentType.NEW_PROJECT, IntentType.GENERAL
        ):
            score -= 0.20
            reasons.append("Workspace appears empty — no files to work with.")
            missing.append("project files in workspace")

        # ── Factor 5: Unresolved symbol references ───────────────────────
        unresolved_syms = [s for s in referenced_symbols if s not in symbols_found]
        if unresolved_syms:
            penalty = min(len(unresolved_syms) * 0.10, 0.20)
            score -= penalty
            reasons.append(f"Symbol(s) not found in workspace: {unresolved_syms[:3]}")
            missing.extend([f"symbol:{s}" for s in unresolved_syms[:3]])

        # ── Factor 6: Very short query for complex intent ─────────────────
        if query_length < 20 and intent in (
            IntentType.IMPLEMENT_SPEC, IntentType.BUG_FIX, IntentType.REFACTOR
        ):
            score -= 0.10
            reasons.append("Request is very short for a complex task — may be ambiguous.")

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        # ── Determine action ─────────────────────────────────────────────
        if score >= THRESHOLD_AUTO_PROCEED:
            action = "proceed"
        elif score >= THRESHOLD_COLLECT_MORE:
            action = "collect_more"
        else:
            action = "ask_user"

        logger.debug(f"Confidence: {score:.2f} → {action} | reasons: {reasons}")

        return ConfidenceResult(
            score=round(score, 2),
            action=action,
            reasons=reasons,
            missing=missing,
        )

    def to_prompt_block(self, result: ConfidenceResult) -> str:
        """Format confidence result as a prompt note (only for collect_more/ask_user)."""
        if result.action == "proceed" or not result.reasons:
            return ""
        lines = [
            "\n[CONTEXT GAP DETECTED]",
            f"Confidence: {result.score:.0%}",
        ]
        if result.reasons:
            lines.append("Missing information:")
            for r in result.reasons:
                lines.append(f"  • {r}")
        if result.action == "collect_more":
            lines.append("→ Collect more context before proceeding.")
        elif result.action == "ask_user":
            lines.append("→ Ask the user for the missing information before proceeding.")
        return "\n".join(lines)
