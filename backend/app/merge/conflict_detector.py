"""
Conflict Detector — Inspects symbol updates and modifications to catch semantic collisions.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Set
from ..patch.patch_store import ProposedPatch

logger = logging.getLogger("devpilot.merge.conflict_detector")


class ConflictDetector:
    """Verifies that parallel agent patches do not overwrite identical code blocks or symbols."""

    def detect_conflicts(self, patches: List[ProposedPatch]) -> List[str]:
        """Scans list of active proposed patches for potential symbol or file conflicts."""
        conflicts = []
        file_modifiers: Dict[str, List[str]] = {}
        symbol_modifiers: Dict[str, List[str]] = {}

        for p in patches:
            # File level tracking
            if p.file_path not in file_modifiers:
                file_modifiers[p.file_path] = []
            file_modifiers[p.file_path].append(p.patch_id)

            # Symbol level tracking
            for symbol in p.metadata.changed_symbols:
                if symbol not in symbol_modifiers:
                    symbol_modifiers[symbol] = []
                symbol_modifiers[symbol].append(p.patch_id)

        # 1. Detect file-level collisions
        for path, patch_ids in file_modifiers.items():
            if len(patch_ids) > 1:
                conflicts.append(
                    f"File Collision: Multiple parallel patches modifying '{path}': {patch_ids}"
                )

        # 2. Detect symbol-level collisions
        for symbol, patch_ids in symbol_modifiers.items():
            if len(patch_ids) > 1:
                conflicts.append(
                    f"Symbol Collision: Multiple parallel patches modifying code symbol '{symbol}': {patch_ids}"
                )

        if conflicts:
            logger.warning(f"Conflict detection found {len(conflicts)} execution block collisions.")
        else:
            logger.info("Conflict detection: No parallel collisions detected.")

        return conflicts


# ── Singleton ───────────────────────────────────────────────────────────────

conflict_detector = ConflictDetector()
