"""
Knowledge Graph — Semantic node-edge model of design patterns, components, and concepts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("devpilot.brain.knowledge_graph")


@dataclass
class KnowledgeNode:
    concept: str
    category: str                       # architectural_pattern | library | convention
    description: str
    related_concepts: set[str] = field(default_factory=set)


class KnowledgeGraph:
    """Stores high-level semantic rules, patterns, and conventions of the workspace."""

    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self._load_base_knowledge()

    def _load_base_knowledge(self) -> None:
        # Register standard conventions of the agent OS architecture
        self.add_concept(
            concept="Microkernel",
            category="architectural_pattern",
            description="Microkernel OS design separating core orchestration logic from specialized extensions."
        )
        self.add_concept(
            concept="API Gateway",
            category="architectural_pattern",
            description="Unified ingress controller enforcing rate limits, circuit breaking, and session safety."
        )

    def add_concept(self, concept: str, category: str, description: str) -> None:
        if concept not in self.nodes:
            self.nodes[concept] = KnowledgeNode(concept=concept, category=category, description=description)

    def link_concepts(self, first: str, second: str) -> None:
        n1 = self.nodes.get(first)
        n2 = self.nodes.get(second)
        if n1 and n2:
            n1.related_concepts.add(second)
            n2.related_concepts.add(first)

    def get_related(self, concept: str) -> list[str]:
        n = self.nodes.get(concept)
        if not n:
            return []
        return list(n.related_concepts)


# ── Singleton ───────────────────────────────────────────────────────────────

knowledge_graph = KnowledgeGraph()
