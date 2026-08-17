"""
Contract Validator — Ensures code changes adhere to generated structural code contracts.
"""
from __future__ import annotations

import logging
import re

from ..intelligence.contract_generator import CodeContract

logger = logging.getLogger("loopix.merge.contract_validator")


class ContractValidator:
    """Verifies interface signatures and db fields are compliant with initial contracts."""

    def validate_code(self, code_content: str, contract: CodeContract) -> list[str]:
        """Validate code_content against a structural contract.

        Returns list of validation violation messages.
        """
        violations = []
        
        # Heuristic checks based on contract type
        if contract.contract_type == "function":
            for signature in contract.signatures:
                if "#" in signature:
                    continue  # skip comment signatures
                # Search for signature matching
                func_name_match = re.search(r'def\s+(\w+)', signature)
                if func_name_match:
                    func_name = func_name_match.group(1)
                    if func_name not in code_content:
                        violations.append(
                            f"Missing required function definition: '{func_name}' "
                            f"as specified in contract '{contract.contract_id}'"
                        )
        elif contract.contract_type == "db":
            for prop in contract.properties:
                if prop not in code_content:
                    violations.append(
                        f"Database schema violates contract. Missing column/property: '{prop}'"
                    )

        if violations:
            logger.warning(
                f"Contract validation failed for component '{contract.component_name}' "
                f"with {len(violations)} violations."
            )
        else:
            logger.info(f"Contract validation passed for component '{contract.component_name}'")

        return violations


# ── Singleton ───────────────────────────────────────────────────────────────

contract_validator = ContractValidator()
