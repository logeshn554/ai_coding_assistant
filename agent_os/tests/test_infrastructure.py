import os
import time
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from agent_os.infrastructure.metrics import MetricsCollector, MetricCounter, MetricGauge
from agent_os.infrastructure.observability import Observability
from agent_os.infrastructure.distributed_tracing import DistributedTracer, TraceSpan
from agent_os.infrastructure.durable_event_bus import DurableEventBus, Event
from agent_os.infrastructure.audit_store import AuditStore, AuditRecord
from agent_os.infrastructure.secret_store import SecretStore
from agent_os.infrastructure.workflow_store import WorkflowStore, WorkflowState
from agent_os.infrastructure.configuration import Configuration

def test_metrics_collector():
    collector = MetricsCollector()
    
    # Check default/empty
    assert collector.get_metric_value("requests") == 0.0
    
    # Increment counter
    collector.increment("requests", value=2.0, labels={"env": "prod"})
    assert collector.get_metric_value("requests", labels={"env": "prod"}) == 2.0
    
    # Increment counter again
    collector.increment("requests", value=1.5, labels={"env": "prod"})
    assert collector.get_metric_value("requests", labels={"env": "prod"}) == 3.5
    
    # Gauge setting
    collector.set_gauge("memory_mb", value=512.0, labels={"host": "localhost"})
    assert collector.get_metric_value("memory_mb", labels={"host": "localhost"}) == 512.0
    
    # All metrics serialization
    all_metrics = collector.get_all_metrics()
    assert "requests{env=prod}" in all_metrics["counters"]
    assert all_metrics["counters"]["requests{env=prod}"] == 3.5
    assert "memory_mb{host=localhost}" in all_metrics["gauges"]
    assert all_metrics["gauges"]["memory_mb{host=localhost}"] == 512.0
    
    # Clear
    collector.clear()
    assert collector.get_metric_value("requests", labels={"env": "prod"}) == 0.0
    assert collector.get_metric_value("memory_mb", labels={"host": "localhost"}) == 0.0


def test_observability():
    obs = Observability()
    
    assert len(obs.get_spans()) == 0
    
    # Run in span
    with obs.span("test_operation", attributes={"context": "unit_test"}):
        time.sleep(0.01)
        
    spans = obs.get_spans()
    assert len(spans) == 1
    assert spans[0]["name"] == "test_operation"
    assert spans[0]["attributes"] == {"context": "unit_test"}
    assert spans[0]["duration_ms"] > 0.0
    
    # Clear spans
    obs.clear_spans()
    assert len(obs.get_spans()) == 0


def test_distributed_tracer():
    tracer = DistributedTracer()
    
    # Start span
    span = tracer.start_span("agent_reasoning", trace_id="my_trace_123")
    assert span.trace_id == "my_trace_123"
    assert span.name == "agent_reasoning"
    assert span.status == "active"
    assert span.span_id is not None
    
    # Get span
    assert tracer.get_span(span.span_id) == span
    
    # Get trace spans
    trace_spans = tracer.get_trace_spans("my_trace_123")
    assert len(trace_spans) == 1
    assert trace_spans[0] == span
    
    # End span
    tracer.end_span(span.span_id, status="success", metadata={"cost": 0.02})
    updated_span = tracer.get_span(span.span_id)
    assert updated_span.status == "success"
    assert updated_span.metadata == {"cost": 0.02}


@pytest.mark.asyncio
async def test_durable_event_bus():
    bus = DurableEventBus()
    
    received_events = []
    
    def sync_handler(event: Event):
        received_events.append(event)
        
    async def async_handler(event: Event):
        received_events.append(event)
        
    # Subscribe
    bus.subscribe("file_change", sync_handler)
    bus.subscribe("file_change", async_handler)
    
    # Publish
    await bus.publish("file_change", data={"file": "main.py"}, correlation_id="corr_1", sender="test")
    
    # Wait a tiny bit for async tasks if needed, though publish awaits them
    assert len(received_events) == 2
    assert received_events[0].event_type == "file_change"
    assert received_events[0].data == {"file": "main.py"}
    assert received_events[0].correlation_id == "corr_1"
    assert received_events[0].sender == "test"
    assert received_events[0].sequence_id == 1
    
    # Replay
    replayed = bus.replay(since_sequence_id=1)
    assert len(replayed) == 1
    assert replayed[0].sequence_id == 1
    
    # Wildcard subscription
    wildcard_received = []
    bus.subscribe("*", lambda e: wildcard_received.append(e))
    await bus.publish("agent_log", data="hello world")
    assert len(wildcard_received) == 1
    assert wildcard_received[0].event_type == "agent_log"
    
    # Unsubscribe
    bus.unsubscribe("file_change", sync_handler)
    received_events.clear()
    await bus.publish("file_change", data={"file": "other.py"})
    assert len(received_events) == 1  # Only async_handler remains
    
    # Clear
    bus.clear_log()
    assert len(bus.get_event_log()) == 0


def test_audit_store():
    store = AuditStore()
    
    # Empty
    assert len(store.get_records()) == 0
    
    # Log actions
    r1 = store.log_action("write_file", "user_1", "config.json", "approved", {"bytes": 100})
    r2 = store.log_action("delete_file", "user_1", "config.json", "denied")
    
    assert len(store.get_records()) == 2
    assert r1.action == "write_file"
    assert r1.record_hash != ""
    assert r2.record_hash != ""
    
    # Check integrity
    assert store.verify_integrity() is True
    
    # Corrupt a record to test validation
    r1.action = "tampered_write_action"
    assert store.verify_integrity() is False


def test_secret_store():
    store = SecretStore()
    
    # Clear any leftover state
    store.clear()
    
    # Set and get secret
    store.set_secret("DATABASE_PASSWORD", "super-secret-123")
    assert store.get_secret("DATABASE_PASSWORD") == "super-secret-123"
    
    # Delete secret
    store.delete_secret("DATABASE_PASSWORD")
    assert store.get_secret("DATABASE_PASSWORD") is None
    
    # Fallback to environment variable
    with patch.dict(os.environ, {"MY_ENV_SECRET": "from-env-var"}):
        assert store.get_secret("MY_ENV_SECRET") == "from-env-var"


def test_workflow_store():
    store = WorkflowStore()
    
    # Empty list
    assert len(store.list_workflows()) == 0
    
    # Save new state
    w1 = store.save_state(
        workflow_id="wf_1",
        workflow_type="coding",
        status="running",
        current_node="generate_code",
        state_data={"attempt": 1}
    )
    
    assert w1.workflow_id == "wf_1"
    assert w1.status == "running"
    assert w1.current_node == "generate_code"
    
    # Retrieve
    retrieved = store.get_state("wf_1")
    assert retrieved == w1
    
    # Update state
    w1_updated = store.save_state(
        workflow_id="wf_1",
        workflow_type="coding",
        status="completed",
        current_node="done",
        state_data={"attempt": 1, "success": True}
    )
    assert w1_updated.status == "completed"
    assert w1_updated.current_node == "done"
    
    # List and filter
    assert len(store.list_workflows(workflow_type="coding")) == 1
    assert len(store.list_workflows(workflow_type="debugging")) == 0
    assert len(store.list_workflows(status="completed")) == 1
    assert len(store.list_workflows(status="failed")) == 0
    
    # Delete and clear
    store.delete_state("wf_1")
    assert store.get_state("wf_1") is None
    
    store.save_state("wf_2", "test", "running", "start", {})
    assert len(store.list_workflows()) == 1
    store.clear()
    assert len(store.list_workflows()) == 0


def test_configuration():
    config = Configuration()
    
    # Default values
    assert config.get("agent_os_mode") == "sandbox"
    assert config.get("max_agent_concurrency") == 4
    
    # Fallback default value
    assert config.get("non_existent_key", "my_fallback") == "my_fallback"
    
    # Set default
    config.set_default("new_default_key", "default_val")
    assert config.get("new_default_key") == "default_val"
    
    # Read from environment variables
    with patch.dict(os.environ, {
        "DEVPILOT_AGENT_OS_MODE": "production",
        "DEVPILOT_MAX_AGENT_CONCURRENCY": "10",
        "DEVPILOT_COST_LIMIT_USD": "25.5",
        "DEVPILOT_DEBUG_MODE": "false"
    }):
        # String conversion
        assert config.get("agent_os_mode") == "production"
        # Integer conversion
        assert config.get("max_agent_concurrency") == 10
        # Float conversion
        assert config.get("cost_limit_usd") == 25.5
        # Boolean conversion
        assert config.get("debug_mode") is False
