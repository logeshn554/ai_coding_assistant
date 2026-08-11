"""
Metrics — Numeric metrics monitoring (success counts, duration timers, rate limits).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("agentos.infrastructure.metrics")


@dataclass
class MetricCounter:
    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0


@dataclass
class MetricGauge:
    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0


class MetricsCollector:
    """Manages simple application performance counters and gauges."""

    def __init__(self) -> None:
        self._counters: Dict[str, MetricCounter] = {}
        self._gauges: Dict[str, MetricGauge] = {}

    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def increment(self, name: str, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """Increment a metric counter."""
        lbls = labels or {}
        key = self._make_key(name, lbls)
        if key not in self._counters:
            self._counters[key] = MetricCounter(name=name, labels=lbls)
        self._counters[key].value += value

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """Set a metric gauge value."""
        lbls = labels or {}
        key = self._make_key(name, lbls)
        if key not in self._gauges:
            self._gauges[key] = MetricGauge(name=name, labels=lbls)
        self._gauges[key].value = value

    def get_metric_value(self, name: str, labels: Dict[str, str] = None) -> float:
        """Retrieve the value of a counter or gauge."""
        lbls = labels or {}
        key = self._make_key(name, lbls)
        
        counter = self._counters.get(key)
        if counter:
            return counter.value
            
        gauge = self._gauges.get(key)
        if gauge:
            return gauge.value
            
        return 0.0

    def get_all_metrics(self) -> Dict[str, Any]:
        """Format metrics for monitoring endpoints."""
        return {
            "counters": {k: c.value for k, c in self._counters.items()},
            "gauges": {k: g.value for k, g in self._gauges.items()}
        }

    def clear(self) -> None:
        self._counters.clear()
        self._gauges.clear()


metrics_collector = MetricsCollector()



