"""
Kernel Health Monitor — Heartbeat monitoring, deadlock detection, and forced termination.

Provides:
  - Heartbeat tracking for long-running agent workers
  - Deadlock detection via timeout thresholds
  - Forced termination of unresponsive workers
  - Health status aggregation for the kernel dashboard
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from agent_os.kernel.interfaces import IKernelService

logger = logging.getLogger("agentos.kernel.health_monitor")


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class WorkerHealth:
    """Health state of a single worker/agent."""
    worker_id: str
    worker_type: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    last_heartbeat: float = 0.0
    started_at: float = field(default_factory=time.time)
    heartbeat_count: int = 0
    consecutive_misses: int = 0
    current_task: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at

    @property
    def time_since_heartbeat(self) -> float:
        if self.last_heartbeat <= 0:
            return time.time() - self.started_at
        return time.time() - self.last_heartbeat


@dataclass
class HealthConfig:
    """Health monitoring configuration."""
    heartbeat_interval: float = 30.0      # expected interval between heartbeats
    miss_threshold: int = 3               # consecutive misses → degraded
    dead_threshold: int = 6               # consecutive misses → dead
    check_interval: float = 15.0          # how often the monitor checks health
    auto_terminate_dead: bool = True      # auto-terminate dead workers


class HealthMonitor(IKernelService):
    """Monitors health of all registered workers/agents."""

    def __init__(self, config: HealthConfig = None):
        self.config = config or HealthConfig()
        self._workers: Dict[str, WorkerHealth] = {}
        self._termination_callbacks: List[Callable[[str, WorkerHealth], None]] = []
        self._status_callbacks: List[Callable[[str, HealthStatus, HealthStatus], None]] = []

    def on_init(self) -> None:
        logger.info("Initializing HealthMonitor service")

    def on_shutdown(self) -> None:
        logger.info("Shutting down HealthMonitor service")
        self._workers.clear()

    def register_worker(self, worker_id: str, worker_type: str = "", task: str = "") -> WorkerHealth:
        """Register a worker for health monitoring."""
        health = WorkerHealth(
            worker_id=worker_id,
            worker_type=worker_type,
            status=HealthStatus.HEALTHY,
            last_heartbeat=time.time(),
            current_task=task,
        )
        self._workers[worker_id] = health
        logger.debug(f"Worker registered for health monitoring: {worker_id}")
        return health

    def unregister_worker(self, worker_id: str) -> None:
        self._workers.pop(worker_id, None)

    def heartbeat(self, worker_id: str, metadata: Dict[str, Any] = None) -> None:
        """Record a heartbeat from a worker."""
        health = self._workers.get(worker_id)
        if health is None:
            health = self.register_worker(worker_id)

        health.last_heartbeat = time.time()
        health.heartbeat_count += 1
        health.consecutive_misses = 0

        if metadata:
            health.metadata.update(metadata)

        old_status = health.status
        health.status = HealthStatus.HEALTHY
        if old_status != HealthStatus.HEALTHY:
            self._notify_status_change(worker_id, old_status, HealthStatus.HEALTHY)

    def update_task(self, worker_id: str, task: str) -> None:
        """Update the current task for a worker."""
        health = self._workers.get(worker_id)
        if health:
            health.current_task = task

    def check_all(self) -> Dict[str, HealthStatus]:
        """Run health check on all registered workers."""
        results = {}
        now = time.time()

        for worker_id, health in list(self._workers.items()):
            time_since = now - (health.last_heartbeat or health.started_at)
            missed = int(time_since / self.config.heartbeat_interval)
            health.consecutive_misses = max(0, missed)

            old_status = health.status

            if missed >= self.config.dead_threshold:
                health.status = HealthStatus.DEAD
            elif missed >= self.config.miss_threshold:
                health.status = HealthStatus.UNHEALTHY
            elif missed >= 1:
                health.status = HealthStatus.DEGRADED
            else:
                health.status = HealthStatus.HEALTHY

            if health.status != old_status:
                self._notify_status_change(worker_id, old_status, health.status)

            # Auto-terminate dead workers
            if health.status == HealthStatus.DEAD and self.config.auto_terminate_dead:
                logger.warning(f"Auto-terminating dead worker: {worker_id}")
                self._terminate_worker(worker_id, health)

            results[worker_id] = health.status

        return results

    def _notify_status_change(self, worker_id: str, old: HealthStatus, new: HealthStatus) -> None:
        logger.info(f"Worker {worker_id} health: {old.value} → {new.value}")
        for callback in self._status_callbacks:
            try:
                callback(worker_id, old, new)
            except Exception:
                pass

    def _terminate_worker(self, worker_id: str, health: WorkerHealth) -> None:
        for callback in self._termination_callbacks:
            try:
                callback(worker_id, health)
            except Exception as e:
                logger.error(f"Termination callback error for {worker_id}: {e}")

    def on_termination(self, callback: Callable[[str, WorkerHealth], None]) -> None:
        self._termination_callbacks.append(callback)

    def on_status_change(self, callback: Callable[[str, HealthStatus, HealthStatus], None]) -> None:
        self._status_callbacks.append(callback)

    def get_worker_health(self, worker_id: str) -> Optional[WorkerHealth]:
        return self._workers.get(worker_id)

    def get_overall_status(self) -> HealthStatus:
        """Aggregate health status across all workers."""
        if not self._workers:
            return HealthStatus.UNKNOWN

        statuses = [h.status for h in self._workers.values()]
        if any(s == HealthStatus.DEAD for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.DEGRADED
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_stats(self) -> Dict[str, Any]:
        statuses = {}
        for h in self._workers.values():
            statuses[h.status.value] = statuses.get(h.status.value, 0) + 1

        return {
            "total_workers": len(self._workers),
            "overall_status": self.get_overall_status().value,
            "status_counts": statuses,
            "workers": {
                wid: {
                    "status": h.status.value,
                    "type": h.worker_type,
                    "task": h.current_task,
                    "uptime": round(h.uptime_seconds, 1),
                    "last_heartbeat_ago": round(h.time_since_heartbeat, 1),
                }
                for wid, h in self._workers.items()
            },
        }


