"""
Intent Compiler — Translates user tasks into structured goals, constraints, and validation criteria.

Enforces:
  - Goal decomposition
  - Directives/constraints extraction
  - Identification of validation/evidence requirements
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("loopix.intelligence.intent_compiler")


@dataclass
class CompiledIntent:
    """The structured translation of user intent."""
    raw_prompt: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    estimated_risk: str = "low"  # low | medium | high
    affected_components: list[str] = field(default_factory=list)


class IntentCompiler:
    """Parses natural language instructions into concrete execution contracts."""

    def compile(self, prompt: str) -> CompiledIntent:
        """Rule-based parsing of user prompts into structured intents.

        Enriches prompt with heuristics and extracts directives.
        """
        prompt_clean = prompt.strip()
        lines = [line.strip() for line in prompt_clean.split("\n") if line.strip()]

        # 1. Goal extraction (use the first line or entire first block)
        goal = lines[0] if lines else "Execute task"
        
        constraints = []
        acceptance_criteria = []
        evidence_requirements = []
        affected_components = []
        risk = "low"

        # Heuristic rules to extract constraints (words like "must", "should", "don't", "avoid", "only")
        must_patterns = [
            r"\bmust\b", r"\bshould\b", r"\bdo\s+not\b", r"\bdon't\b", r"\bavoid\b",
            r"\bnever\b", r"\bonly\b", r"\brequires?\b"
        ]

        for line in lines:
            line_lower = line.lower()
            if any(re.search(pat, line_lower) for pat in must_patterns):
                constraints.append(line)

            # Heuristics for acceptance criteria / tests
            if any(kw in line_lower for kw in ["test", "verify", "validate", "assert", "check"]):
                acceptance_criteria.append(line)

            # Heuristics for evidence / output artifacts
            if any(kw in line_lower for kw in ["write", "file", "generate", "create", "output", "commit"]):
                evidence_requirements.append(line)

            # High risk markers
            if any(kw in line_lower for kw in ["delete", "remove", "wipe", "refactor", "overwrite", "critical", "security"]):
                risk = "medium"
                if any(kw in line_lower for kw in ["all", "everything", "force", "hard reset"]):
                    risk = "high"

        # Build list of affected components (heuristic paths or files)
        paths = re.findall(r'[\w\-./\\]+\.\w+', prompt)
        for p in paths:
            if not p.startswith(("http:", "https:")):
                affected_components.append(p)

        # Defaults if lists are empty
        if not constraints:
            constraints.append("Enforce existing style and architecture invariants.")
        if not acceptance_criteria:
            acceptance_criteria.append("The project compiles and automated tests pass.")
        if not evidence_requirements:
            evidence_requirements.append("Code changes must be verified using verification runners.")

        compiled = CompiledIntent(
            raw_prompt=prompt,
            goal=goal,
            constraints=constraints,
            acceptance_criteria=acceptance_criteria,
            evidence_requirements=evidence_requirements,
            estimated_risk=risk,
            affected_components=list(set(affected_components)),
        )

        logger.info(f"Compiled prompt of size {len(prompt)}: Risk={compiled.estimated_risk}, Goal='{compiled.goal[:60]}'")
        return compiled


# ── Singleton ───────────────────────────────────────────────────────────────

intent_compiler = IntentCompiler()
