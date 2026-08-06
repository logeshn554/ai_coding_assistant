"""
Audit Store — Append-only trace logger tracking security-sensitive activities.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentos.infrastructure.audit_store")


@dataclass
class AuditRecord:
    """An entry in the append-only audit trail."""
    action: str
    actor: str                  # agent_type, user_id, system
    target: str                 # file path, command string, etc.
    status: str                 # approved, denied, error
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    record_hash: str = ""


class AuditStore:
    """Provides tamper-evident record tracking for compliance auditing."""

    def __init__(self) -> None:
        self._records: List[AuditRecord] = []
        self._last_hash = "genesis"

    def log_action(self, action: str, actor: str, target: str, status: str, details: Optional[Dict[str, Any]] = None) -> AuditRecord:
        """Append a new record to the audit chain."""
        now = time.time()
        record_details = details or {}
        
        # Calculate secure chain hash
        raw_to_hash = f"{action}:{actor}:{target}:{status}:{now}:{record_details}:{self._last_hash}"
        current_hash = hashlib.sha256(raw_to_hash.encode()).hexdigest()
        
        record = AuditRecord(
            action=action,
            actor=actor,
            target=target,
            status=status,
            timestamp=now,
            details=record_details,
            record_hash=current_hash
        )

        self._records.append(record)
        self._last_hash = current_hash
        logger.info(f"[Audit Log] {action} by {actor} on {target} -> {status} (hash: {current_hash[:8]})")
        return record

    def verify_integrity(self) -> bool:
        """Verify the integrity of the audit chain by recalculating all hashes."""
        current_hash = "genesis"
        for record in self._records:
            raw_to_hash = f"{record.action}:{record.actor}:{record.target}:{record.status}:{record.timestamp}:{record.details}:{current_hash}"
            expected_hash = hashlib.sha256(raw_to_hash.encode()).hexdigest()
            if record.record_hash != expected_hash:
                logger.error(f"Audit log corruption detected! Record hash mismatch. Expected {expected_hash}, got {record.record_hash}")
                return False
            current_hash = record.record_hash
        return True

    def get_records(self) -> List[AuditRecord]:
        return list(self._records)


# ── Singleton ───────────────────────────────────────────────────────────────

audit_store = AuditStore()
