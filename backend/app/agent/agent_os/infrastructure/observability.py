"""
Observability — Logging, performance timing, and health status indicators.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("agentos.infrastructure.observability")


class Observability:
    """Collects spans, logs, and execution summaries for agent activity."""

    def __init__(self) -> None:
        self._spans: List[Dict[str, Any]] = []

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[None, None, None]:
        """Context manager to measure execution time of a code block."""
        start = time.perf_counter()
        span_id = f"span_{int(start * 1000)}"
        attrs = attributes or {}
        logger.debug(f"[Span Start] {name} ({span_id}) with {attrs}")
        try:
            yield
        finally:
            duration = (time.perf_counter() - start) * 1000.0
            self._spans.append({
                "span_id": span_id,
                "name": name,
                "duration_ms": duration,
                "attributes": attrs,
                "timestamp": time.time(),
            })
            logger.debug(f"[Span End] {name} ({span_id}) completed in {duration:.2f}ms")

    def get_spans(self) -> List[Dict[str, Any]]:
        return list(self._spans)

    def clear_spans(self) -> None:
        self._spans.clear()


observability = Observability()



