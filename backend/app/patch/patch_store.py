"""
Patch Store — Persistent database of proposed patches and diffs before they are merged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .patch_metadata import PatchMetadata

logger = logging.getLogger("devpilot.patch.patch_store")


@dataclass
class ProposedPatch:
    patch_id: str
    file_path: str
    diff_content: str
    metadata: PatchMetadata
    status: str = "proposed"            # proposed | merged | rejected | rolled_back


class PatchStore:
    """Stores patches produced by agent workers before transaction commit."""

    def __init__(self) -> None:
        self._patches: Dict[str, ProposedPatch] = {}

    def add_patch(self, patch_id: str, file_path: str, diff_content: str, metadata: PatchMetadata) -> ProposedPatch:
        patch = ProposedPatch(
            patch_id=patch_id,
            file_path=file_path,
            diff_content=diff_content,
            metadata=metadata
        )
        self._patches[patch_id] = patch
        logger.info(f"Added proposed patch '{patch_id}' for file '{file_path}' (symbols={metadata.changed_symbols})")
        return patch

    def get_patch(self, patch_id: str) -> Optional[ProposedPatch]:
        return self._patches.get(patch_id)

    def list_patches_for_file(self, file_path: str) -> List[ProposedPatch]:
        return [p for p in self._patches.values() if p.file_path == file_path]

    def update_status(self, patch_id: str, status: str) -> None:
        patch = self._patches.get(patch_id)
        if patch:
            patch.status = status
            logger.debug(f"Updated status of patch '{patch_id}' to: {status}")


# ── Singleton ───────────────────────────────────────────────────────────────

patch_store = PatchStore()
