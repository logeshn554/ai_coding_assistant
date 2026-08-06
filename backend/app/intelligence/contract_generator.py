"""
Contract Generator — Generates API schemas, shared types, database contracts, and function signatures.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from .intent_compiler import CompiledIntent

logger = logging.getLogger("devpilot.intelligence.contract_generator")


@dataclass
class CodeContract:
    """A contract defining API schemas, database fields, or function signatures."""
    contract_id: str
    component_name: str
    contract_type: str                  # api | db | function | event
    description: str
    signatures: List[str]
    properties: Dict[str, str]
    allowed_mutations: List[str]


class ContractGenerator:
    """Generates execution contracts that agent workers must adhere to."""

    def generate_contract(self, intent: CompiledIntent, component_name: str) -> CodeContract:
        """Derive code signatures and structural contracts based on the compiled intent."""
        contract_type = "function"
        description = f"Contract for {component_name} satisfying: {intent.goal}"
        signatures = []
        properties = {}
        allowed_mutations = ["read"]

        # Infer contract type and mutations
        comp_lower = component_name.lower()
        if "route" in comp_lower or "api" in comp_lower or "endpoint" in comp_lower:
            contract_type = "api"
            signatures.append(f"GET /api/v1/{component_name.replace('_', '-')}")
            properties = {"response_type": "application/json", "auth": "required"}
            allowed_mutations = ["read"]
        elif "db" in comp_lower or "model" in comp_lower or "schema" in comp_lower:
            contract_type = "db"
            properties = {"id": "UUID (PK)", "created_at": "Timestamp", "updated_at": "Timestamp"}
            allowed_mutations = ["read", "insert", "update"]
        else:
            # Code/Function contract
            signatures.append(f"def process_{component_name}(*args, **kwargs) -> Any:")
            allowed_mutations = ["read", "write"]

        # Parse specific function or property directives if mentioned in the prompt
        for path in intent.affected_components:
            if component_name in path:
                signatures.append(f"# Linked to file path: {path}")

        contract = CodeContract(
            contract_id=f"contract_{component_name}_{len(signatures)}",
            component_name=component_name,
            contract_type=contract_type,
            description=description,
            signatures=signatures,
            properties=properties,
            allowed_mutations=allowed_mutations,
        )

        logger.info(f"Generated {contract_type} contract for {component_name} with {len(signatures)} signatures")
        return contract


# ── Singleton ───────────────────────────────────────────────────────────────

contract_generator = ContractGenerator()
