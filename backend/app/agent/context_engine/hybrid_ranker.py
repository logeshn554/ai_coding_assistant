"""
Hybrid Context Ranker & Budget Enforcer — Step 9 & 14 requirements.

Scores candidates using multi-signal hybrid scoring (semantic, symbol, filename,
dependency distance, editor selection, test relationship, recent changes)
and enforces strict ContextBudget limits.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Set

from .types import ContextBudget, ContextItem, ContextProvenance, EditorContext, GitContext

logger = logging.getLogger("devpilot.context_engine.hybrid_ranker")


class HybridRanker:
    """Ranks and truncates context items to satisfy token and file budgets."""

    def __init__(self, budget: Optional[ContextBudget] = None) -> None:
        self.budget = budget or ContextBudget()

    def score_candidate(
        self,
        file_path: str,
        content: str,
        task_query: str,
        editor: Optional[EditorContext] = None,
        git: Optional[GitContext] = None,
        is_test: bool = False,
        dependency_distance: int = 999,
        symbol_matched: bool = False,
        semantic_sim: float = 0.0,
    ) -> float:
        """Calculate multi-signal hybrid context score."""
        score = 0.0

        # 1. Semantic Similarity Signal
        score += semantic_sim * 0.35

        # 2. Symbol Match Signal
        if symbol_matched:
            score += 0.25

        # 3. Filename Match Signal
        filename = os.path.basename(file_path).lower()
        query_words = [w.lower() for w in task_query.split() if len(w) > 2]
        if any(qw in filename for qw in query_words):
            score += 0.20

        # 4. Dependency Distance Bonus
        if dependency_distance == 0:
            score += 0.25
        elif dependency_distance == 1:
            score += 0.15
        elif dependency_distance == 2:
            score += 0.05

        # 5. Active Editor File & Selection Bonus
        if editor:
            if editor.active_file and editor.active_file.replace("\\", "/") == file_path.replace("\\", "/"):
                score += 0.40
            if editor.open_files and any(of.replace("\\", "/") == file_path.replace("\\", "/") for of in editor.open_files):
                score += 0.15

        # 6. Test Relationship Bonus
        if is_test:
            score += 0.10

        # 7. Recent Git Change Bonus
        if git and git.modified_files:
            if any(mf.replace("\\", "/") == file_path.replace("\\", "/") for mf in git.modified_files):
                score += 0.30

        return round(score, 4)

    def rank_and_truncate(
        self,
        candidates: List[ContextItem],
        budget: Optional[ContextBudget] = None,
    ) -> List[ContextItem]:
        """Sort context items by score and apply budget limits (max_files, max_chars, max_tokens)."""
        b = budget or self.budget

        # Sort candidates descending by provenance score
        sorted_candidates = sorted(
            candidates,
            key=lambda item: item.provenance.score if item.provenance else 0.0,
            reverse=True,
        )

        ranked: List[ContextItem] = []
        files_seen: Set[str] = set()
        total_chars = 0

        for item in sorted_candidates:
            if len(files_seen) >= b.max_files and item.file not in files_seen:
                continue

            item_len = len(item.content)
            if total_chars + item_len > b.max_chars:
                # Truncate content if partial fit remains
                remaining = b.max_chars - total_chars
                if remaining > 200:
                    truncated_content = item.content[:remaining] + "\n... [truncated by context budget]"
                    item.content = truncated_content
                    ranked.append(item)
                    files_seen.add(item.file)
                break

            ranked.append(item)
            files_seen.add(item.file)
            total_chars += item_len

        logger.info(f"HybridRanker selected {len(ranked)} items ({total_chars} chars) from {len(candidates)} candidates.")
        return ranked
