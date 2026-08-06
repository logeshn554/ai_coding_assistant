"""
Lease Manager — Manages time-bounded execution leases on workspace resources.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger("devpilot.work_graph.lease_manager")


@dataclass
class Lease:
    lease_id: str
    resource: str
    owner: str
    expires_at: float


class LeaseManager:
    """Evicts stalled execution workers by expiring leases after a timeout."""

    def __init__(self) -> None:
        self._leases: Dict[str, Lease] = {}

    def acquire_lease(self, resource: str, owner: str, duration_seconds: float = 60.0) -> Optional[str]:
        """Acquire a lease on a workspace resource."""
        now = time.time()
        existing = self._leases.get(resource)

        if existing and now < existing.expires_at:
            if existing.owner == owner:
                existing.expires_at = now + duration_seconds
                return existing.lease_id
            logger.warning(f"Lease on '{resource}' currently held by '{existing.owner}'")
            return None

        lease_id = f"lease_{int(now)}_{owner[:4]}"
        self._leases[resource] = Lease(
            lease_id=lease_id,
            resource=resource,
            owner=owner,
            expires_at=now + duration_seconds
        )
        logger.debug(f"Acquired lease {lease_id} on '{resource}' for {owner} (expires in {duration_seconds}s)")
        return lease_id

    def release_lease(self, resource: str, lease_id: str) -> bool:
        lease = self._leases.get(resource)
        if not lease:
            return True

        if lease.lease_id != lease_id:
            return False

        del self._leases[resource]
        logger.debug(f"Released lease {lease_id} on '{resource}'")
        return True

    def check_expired(self) -> None:
        """Scan and clear expired leases."""
        now = time.time()
        expired = [res for res, lease in self._leases.items() if now >= lease.expires_at]
        for res in expired:
            logger.info(f"Lease expired on '{res}' owned by '{self._leases[res].owner}'")
            del self._leases[res]


# ── Singleton ───────────────────────────────────────────────────────────────

lease_manager = LeaseManager()
