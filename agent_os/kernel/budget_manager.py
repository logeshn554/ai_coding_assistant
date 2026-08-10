"""
Kernel Budget Manager — Per-session and per-agent token/cost budget tracking.

Provides:
  - Budget allocation and consumption tracking
  - Budget alerts via event bus
  - Per-agent-type budget policies
  - Session-level budget aggregation
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from agent_os.kernel.interfaces import IKernelService

logger = logging.getLogger("agentos.kernel.budget_manager")


class BudgetScope(str, Enum):
    SESSION = "session"
    AGENT = "agent"
    TENANT = "tenant"
    GLOBAL = "global"


@dataclass
class BudgetAllocation:
    """Budget allocation for a scope."""
    scope: BudgetScope
    scope_id: str
    max_tokens: int = 0            # 0 = unlimited
    max_cost_usd: float = 0.0     # 0 = unlimited
    max_api_calls: int = 0        # 0 = unlimited
    max_duration_seconds: float = 0  # 0 = unlimited

    consumed_tokens: int = 0
    consumed_cost_usd: float = 0.0
    consumed_api_calls: int = 0
    started_at: float = field(default_factory=time.time)

    @property
    def tokens_remaining(self) -> int:
        if self.max_tokens <= 0:
            return 999_999_999
        return max(0, self.max_tokens - self.consumed_tokens)

    @property
    def cost_remaining(self) -> float:
        if self.max_cost_usd <= 0:
            return 999_999.0
        return max(0.0, self.max_cost_usd - self.consumed_cost_usd)

    @property
    def api_calls_remaining(self) -> int:
        if self.max_api_calls <= 0:
            return 999_999
        return max(0, self.max_api_calls - self.consumed_api_calls)

    @property
    def time_remaining(self) -> float:
        if self.max_duration_seconds <= 0:
            return 999_999.0
        elapsed = time.time() - self.started_at
        return max(0.0, self.max_duration_seconds - elapsed)

    @property
    def is_exhausted(self) -> bool:
        if self.max_tokens > 0 and self.consumed_tokens >= self.max_tokens:
            return True
        if self.max_cost_usd > 0 and self.consumed_cost_usd >= self.max_cost_usd:
            return True
        if self.max_api_calls > 0 and self.consumed_api_calls >= self.max_api_calls:
            return True
        if self.max_duration_seconds > 0 and self.time_remaining <= 0:
            return True
        return False

    @property
    def utilization(self) -> float:
        """Overall budget utilization (0.0 to 1.0)."""
        ratios = []
        if self.max_tokens > 0:
            ratios.append(self.consumed_tokens / self.max_tokens)
        if self.max_cost_usd > 0:
            ratios.append(self.consumed_cost_usd / self.max_cost_usd)
        if self.max_api_calls > 0:
            ratios.append(self.consumed_api_calls / self.max_api_calls)
        return max(ratios) if ratios else 0.0


class BudgetAlert(str, Enum):
    WARNING_75 = "budget_warning_75"
    WARNING_90 = "budget_warning_90"
    EXHAUSTED = "budget_exhausted"
    DURATION_WARNING = "budget_duration_warning"


class BudgetManager(IKernelService):
    """Manages budget allocations across sessions and agents."""

    def __init__(self):
        self._allocations: Dict[str, BudgetAllocation] = {}
        self._alert_callbacks: List[Callable[[BudgetAlert, BudgetAllocation], None]] = []
        self._fired_alerts: Dict[str, set] = {}  # scope_id -> set of fired alerts

        # Default budget policies per agent type
        self._agent_defaults: Dict[str, Dict[str, Any]] = {
            "code": {"max_tokens": 500_000, "max_cost_usd": 2.0},
            "test": {"max_tokens": 200_000, "max_cost_usd": 1.0},
            "review": {"max_tokens": 150_000, "max_cost_usd": 0.5},
            "docs": {"max_tokens": 100_000, "max_cost_usd": 0.3},
            "security": {"max_tokens": 150_000, "max_cost_usd": 0.5},
            "debug": {"max_tokens": 300_000, "max_cost_usd": 1.5},
        }

    def on_init(self) -> None:
        logger.info("Initializing BudgetManager service")

    def on_shutdown(self) -> None:
        logger.info("Shutting down BudgetManager service")
        self.reset()

    def add_alert_callback(self, callback: Callable[[BudgetAlert, BudgetAllocation], None]) -> None:
        self._alert_callbacks.append(callback)

    def allocate(
        self,
        scope: BudgetScope,
        scope_id: str,
        max_tokens: int = 0,
        max_cost_usd: float = 0.0,
        max_api_calls: int = 0,
        max_duration_seconds: float = 0.0,
    ) -> BudgetAllocation:
        """Create or update a budget allocation."""
        key = f"{scope.value}:{scope_id}"
        allocation = BudgetAllocation(
            scope=scope,
            scope_id=scope_id,
            max_tokens=max_tokens,
            max_cost_usd=max_cost_usd,
            max_api_calls=max_api_calls,
            max_duration_seconds=max_duration_seconds,
        )
        self._allocations[key] = allocation
        self._fired_alerts[key] = set()
        logger.debug(f"Budget allocated: {key} (tokens={max_tokens}, cost=${max_cost_usd})")
        return allocation

    def allocate_for_agent(self, agent_type: str, agent_id: str) -> BudgetAllocation:
        """Allocate budget based on agent type defaults."""
        defaults = self._agent_defaults.get(agent_type, {"max_tokens": 200_000, "max_cost_usd": 1.0})
        return self.allocate(
            scope=BudgetScope.AGENT,
            scope_id=agent_id,
            max_tokens=defaults.get("max_tokens", 0),
            max_cost_usd=defaults.get("max_cost_usd", 0.0),
        )

    def consume(
        self,
        scope: BudgetScope,
        scope_id: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
        api_calls: int = 0,
    ) -> BudgetAllocation:
        """Record resource consumption and check for alerts."""
        key = f"{scope.value}:{scope_id}"
        allocation = self._allocations.get(key)
        if allocation is None:
            # Auto-allocate with no limits
            allocation = self.allocate(scope, scope_id)

        allocation.consumed_tokens += tokens
        allocation.consumed_cost_usd += cost_usd
        allocation.consumed_api_calls += api_calls

        # Check alert thresholds
        self._check_alerts(key, allocation)

        return allocation

    def _check_alerts(self, key: str, allocation: BudgetAllocation) -> None:
        fired = self._fired_alerts.get(key, set())

        utilization = allocation.utilization

        if allocation.is_exhausted and BudgetAlert.EXHAUSTED not in fired:
            fired.add(BudgetAlert.EXHAUSTED)
            self._fire_alert(BudgetAlert.EXHAUSTED, allocation)
        elif utilization >= 0.9 and BudgetAlert.WARNING_90 not in fired:
            fired.add(BudgetAlert.WARNING_90)
            self._fire_alert(BudgetAlert.WARNING_90, allocation)
        elif utilization >= 0.75 and BudgetAlert.WARNING_75 not in fired:
            fired.add(BudgetAlert.WARNING_75)
            self._fire_alert(BudgetAlert.WARNING_75, allocation)

        self._fired_alerts[key] = fired

    def _fire_alert(self, alert: BudgetAlert, allocation: BudgetAllocation) -> None:
        logger.warning(f"Budget alert: {alert.value} for {allocation.scope.value}:{allocation.scope_id} "
                      f"(utilization={allocation.utilization:.1%})")
        for callback in self._alert_callbacks:
            try:
                callback(alert, allocation)
            except Exception as e:
                logger.error(f"Budget alert callback error: {e}")

    def get_allocation(self, scope: BudgetScope, scope_id: str) -> Optional[BudgetAllocation]:
        key = f"{scope.value}:{scope_id}"
        return self._allocations.get(key)

    def is_within_budget(self, scope: BudgetScope, scope_id: str) -> bool:
        allocation = self.get_allocation(scope, scope_id)
        if allocation is None:
            return True
        return not allocation.is_exhausted

    def get_all_stats(self) -> Dict[str, Any]:
        stats = {}
        for key, alloc in self._allocations.items():
            stats[key] = {
                "utilization": round(alloc.utilization, 3),
                "tokens": f"{alloc.consumed_tokens}/{alloc.max_tokens or '∞'}",
                "cost": f"${alloc.consumed_cost_usd:.4f}/${alloc.max_cost_usd or '∞'}",
                "exhausted": alloc.is_exhausted,
            }
        return stats

    def reset(self, scope: BudgetScope = None, scope_id: str = "") -> None:
        if scope is None:
            self._allocations.clear()
            self._fired_alerts.clear()
            return
        key = f"{scope.value}:{scope_id}"
        self._allocations.pop(key, None)
        self._fired_alerts.pop(key, None)


