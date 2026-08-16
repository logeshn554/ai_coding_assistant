"""
Patch Metadata — Schema definition for metadata attached to proposed patches.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatchMetadata:
    author_agent: str
    changed_symbols: list[str] = field(default_factory=list)
    confidence_score: float = 1.0
    assumptions: list[str] = field(default_factory=list)
    rollback_patch_id: str = ""
    timestamp: float = field(default_factory=time.time)
    extra_details: dict[str, Any] = field(default_factory=dict)
