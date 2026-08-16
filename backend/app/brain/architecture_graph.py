"""
Architecture Graph — High-level structural hierarchy of systems and layers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("devpilot.brain.architecture_graph")


@dataclass
class ComponentNode:
    name: str
    layer: str                          # gateway | kernel | database | frontend | agent_pool
    sub_components: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)


class ArchitectureGraph:
    """Represents the static structure of layers and component invariants."""

    def __init__(self) -> None:
        self.components: dict[str, ComponentNode] = {}
        self._load_base_architecture()

    def _load_base_architecture(self) -> None:
        # Load high level layout corresponding to the 16-layer Agentic OS diagram
        self.register_component(
            ComponentNode(
                name="Gateway",
                layer="gateway",
                sub_components=["Auth", "RateLimiter", "CircuitBreaker", "Streaming", "SessionManager"]
            )
        )
        self.register_component(
            ComponentNode(
                name="Microkernel",
                layer="kernel",
                sub_components=["BudgetManager", "HealthMonitor", "CancellationManager", "PolicyEngine"]
            )
        )

    def register_component(self, node: ComponentNode) -> None:
        self.components[node.name] = node
        logger.debug(f"Registered architecture component: {node.name} (layer={node.layer})")

    def get_components_by_layer(self, layer: str) -> list[ComponentNode]:
        return [c for c in self.components.values() if c.layer == layer]


# ── Singleton ───────────────────────────────────────────────────────────────

architecture_graph = ArchitectureGraph()
