"""
Distributed Tracing — Propagates execution spans across remote workers and subagents.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentos.infrastructure.distributed_tracing")


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str = ""
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)


class DistributedTracer:
    """Manages cross-cutting transaction spans for multi-agent workflows."""

    def __init__(self) -> None:
        self._spans: Dict[str, TraceSpan] = {}

    def start_span(self, name: str, trace_id: Optional[str] = None, parent_span_id: Optional[str] = None) -> TraceSpan:
        """Initialize a new trace span."""
        t_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        s_id = f"span_{uuid.uuid4().hex[:8]}"
        
        span = TraceSpan(
            trace_id=t_id,
            span_id=s_id,
            parent_span_id=parent_span_id,
            name=name,
            status="active"
        )
        self._spans[s_id] = span
        logger.debug(f"[Trace Start] {name} (trace: {t_id}, span: {s_id}, parent: {parent_span_id})")
        return span

    def end_span(self, span_id: str, status: str = "success", metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark a span as completed."""
        span = self._spans.get(span_id)
        if span:
            span.status = status
            if metadata:
                span.metadata.update(metadata)
            logger.debug(f"[Trace End] {span.name} (span: {span_id}) completed with status: {status}")

    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        return self._spans.get(span_id)

    def get_trace_spans(self, trace_id: str) -> List[TraceSpan]:
        """Get all spans associated with a particular trace transaction."""
        return [s for s in self._spans.values() if s.trace_id == trace_id]


# ── Singleton ───────────────────────────────────────────────────────────────

distributed_tracer = DistributedTracer()
