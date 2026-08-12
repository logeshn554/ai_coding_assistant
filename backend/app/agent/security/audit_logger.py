"""
Security Audit Logger — Step 24 requirement.

Logs structured, secret-redacted security audit entries for every sensitive operation,
permission decision, or boundary check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from .secret_redactor import SecretRedactor

logger = logging.getLogger("devpilot.security.audit")


@dataclass
class AuditRecord:
    session_id: str
    action: str
    resource: str
    risk: str
    decision: str  # APPROVED | DENIED | REJECTED | PENDING
    command: Optional[str] = None
    files_affected: List[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "action": self.action,
            "resource": self.resource,
            "risk": self.risk,
            "decision": self.decision,
            "command": SecretRedactor.redact_secrets(self.command) if self.command else None,
            "files_affected": [SecretRedactor.redact_secrets(f) for f in self.files_affected],
        }


class AuditLogger:
    """Records security audit entries to persistent log files and standard loggers."""

    def __init__(self, log_dir: Optional[str] = None) -> None:
        self.log_dir = log_dir
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    def log_record(self, record: AuditRecord) -> Dict[str, Any]:
        data = record.to_dict()
        logger.info(f"SECURITY AUDIT: [{record.decision}] {record.action} on {record.resource} (Risk: {record.risk})")

        if self.log_dir:
            log_path = os.path.join(self.log_dir, "security_audit.jsonl")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data) + "\n")
            except Exception as e:
                logger.error(f"Failed writing audit record: {e}")

        return data
