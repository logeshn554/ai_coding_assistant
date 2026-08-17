"""
Phase 11: Project Knowledge & Long-Term Memory.

Stores durable project facts (architectural conventions, testing commands, key APIs)
with explicit provenance (source file, timestamp) and invalidation tracking when source files change.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectFact:
    fact_id: str
    category: str  # architecture | convention | api | testing | build
    statement: str
    source_file: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    is_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "category": self.category,
            "statement": self.statement,
            "source_file": self.source_file,
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
        }


class ProjectMemoryStore:
    """Persistent storage for durable project facts and conventions."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.facts: dict[str, ProjectFact] = {}
        self._load_memory()

    def _get_memory_path(self) -> str:
        loopix_dir = os.path.join(self.workspace_root, ".loopix")
        os.makedirs(loopix_dir, exist_ok=True)
        return os.path.join(loopix_dir, "project_memory.json")

    def _load_memory(self) -> None:
        path = self._get_memory_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("facts", []):
                        fact = ProjectFact(**item)
                        self.facts[fact.fact_id] = fact
            except Exception:
                pass

    def save_memory(self) -> None:
        path = self._get_memory_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"facts": [f.to_dict() for f in self.facts.values()]}, f, indent=2)
        except Exception:
            pass

    def add_fact(self, category: str, statement: str, source_file: str) -> ProjectFact:
        fid = f"fact_{category}_{len(self.facts)+1}"
        fact = ProjectFact(fact_id=fid, category=category, statement=statement, source_file=source_file)
        self.facts[fid] = fact
        self.save_memory()
        return fact

    def invalidate_source_file(self, modified_source_file: str) -> list[str]:
        """Invalidate all facts derived from modified_source_file."""
        invalidated = []
        for fid, fact in self.facts.items():
            if fact.is_valid and fact.source_file == modified_source_file:
                fact.is_valid = False
                invalidated.append(fid)
        if invalidated:
            self.save_memory()
        return invalidated

    def get_valid_facts(self) -> list[ProjectFact]:
        return [f for f in self.facts.values() if f.is_valid]
