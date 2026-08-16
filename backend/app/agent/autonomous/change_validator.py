"""
Change-Set Validation Engine — Step 15 requirement.

Validates workspace diffs against task contract scope to flag unexpected file edits,
secret leaks, generated artifacts, or lockfile mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .task_contract import AgentTaskContract


@dataclass
class ValidationFinding:
    severity: str  # WARNING | ERROR | CRITICAL
    message: str
    file: str


@dataclass
class ValidationResult:
    valid: bool
    requires_review: bool
    findings: list[ValidationFinding] = field(default_factory=list)


class ChangeSetValidator:
    """Validates diffs against task scope boundaries."""

    @classmethod
    def validate_changes(
        self,
        changed_files: list[str],
        contract: AgentTaskContract,
    ) -> ValidationResult:
        findings: list[ValidationFinding] = []
        requires_review = False

        for f in changed_files:
            norm_f = f.replace("\\", "/").strip("/")

            # Secret file check
            if any(sec in norm_f for sec in [".env", "secret", "credentials", ".pem", ".key"]):
                findings.append(ValidationFinding(severity="CRITICAL", message="Secret or env file modified", file=norm_f))
                requires_review = True

            # Lockfile mutation check
            if norm_f in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock"):
                findings.append(ValidationFinding(severity="WARNING", message="Lockfile modified without explicit request", file=norm_f))
                requires_review = True

            # Out of scope check if scope specified
            if contract.scope:
                if not any(sc.lower() in norm_f.lower() for sc in contract.scope):
                    findings.append(ValidationFinding(severity="WARNING", message=f"Modified file outside task scope ({contract.scope})", file=norm_f))

        valid = not any(f.severity == "CRITICAL" for f in findings)
        return ValidationResult(
            valid=valid,
            requires_review=requires_review or len(findings) > 0,
            findings=findings,
        )
