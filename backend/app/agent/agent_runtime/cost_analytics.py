"""
Phase 13: Model Routing, Performance & Cost Optimization.

Classifies task complexity (FAST, MEDIUM, DEEP) and tracks performance metrics
(latency, token usage, cost, success rate, repair rounds) for cost analytics dashboard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class TaskComplexity(str, Enum):
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    DEEP = "DEEP"


@dataclass
class ExecutionMetric:
    task_id: str
    complexity: TaskComplexity
    duration_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    success: bool
    repair_rounds: int = 0


class CostAnalyticsTracker:
    """Tracks latency, token usage, cost, and task metrics across task complexity tiers."""

    def __init__(self) -> None:
        self.metrics: List[ExecutionMetric] = []

    def record_execution(
        self,
        task_id: str,
        complexity: TaskComplexity,
        duration_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool,
        repair_rounds: int = 0,
    ) -> ExecutionMetric:
        # Estimated cost per 1K tokens ($0.0015 / 1K input, $0.002 / 1K output)
        cost = (prompt_tokens * 0.0000015) + (completion_tokens * 0.000002)
        metric = ExecutionMetric(
            task_id=task_id,
            complexity=complexity,
            duration_ms=duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost, 6),
            success=success,
            repair_rounds=repair_rounds,
        )
        self.metrics.append(metric)
        return metric

    def get_dashboard_summary(self) -> Dict[str, Any]:
        total = len(self.metrics)
        if total == 0:
            return {
                "total_tasks": 0,
                "success_rate_pct": 100.0,
                "avg_latency_ms": 0.0,
                "avg_tokens_per_task": 0,
                "total_cost_usd": 0.0,
                "avg_repair_rounds": 0.0,
            }

        successes = sum(1 for m in self.metrics if m.success)
        total_lat = sum(m.duration_ms for m in self.metrics)
        total_tokens = sum(m.prompt_tokens + m.completion_tokens for m in self.metrics)
        total_cost = sum(m.cost_usd for m in self.metrics)
        total_repairs = sum(m.repair_rounds for m in self.metrics)

        return {
            "total_tasks": total,
            "success_rate_pct": round((successes / total) * 100.0, 2),
            "avg_latency_ms": round(total_lat / total, 2),
            "avg_tokens_per_task": int(total_tokens / total),
            "total_cost_usd": round(total_cost, 4),
            "avg_repair_rounds": round(total_repairs / total, 2),
        }
