import time
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from backend.app.gateway.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerRegistry
)
from backend.app.gateway.rate_limiter import (
    RateLimiter,
    RateLimitRule,
    RateLimitResult,
    SlidingWindowCounter
)
from backend.app.gateway.session_manager import (
    GatewaySessionManager,
    SessionState
)
from backend.app.gateway.streaming import (
    StreamManager,
    StreamConfig,
    StreamState
)

# ── Circuit Breaker Tests ───────────────────────────────────────────────────

def test_circuit_breaker_flow():
    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=0.1,
        window_seconds=10.0,
        min_calls_before_trip=2
    )
    
    cb = CircuitBreaker(name="test_provider", config=config)
    
    # CLOSED state initially
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True
    
    # Trigger failures to open circuit
    cb.record_failure("error 1")
    cb.record_failure("error 2")
    cb.record_failure("error 3")
    
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False
    
    # Wait for timeout to transition to HALF_OPEN
    time.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN
    
    # Success threshold test (needs 2 successes to close)
    assert cb.can_execute() is True
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    
    assert cb.can_execute() is True
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_half_open_failure():
    config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=2,
        timeout_seconds=0.05,
        half_open_max_calls=1
    )
    cb = CircuitBreaker(name="test_provider", config=config)
    
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    
    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN
    
    # Any failure in HALF_OPEN trips it immediately back to OPEN
    cb.record_failure("half open fail")
    assert cb.state == CircuitState.OPEN


def test_circuit_breaker_registry_fallbacks():
    registry = CircuitBreakerRegistry()
    
    cb_primary = registry.get_or_create("primary")
    cb_secondary = registry.get_or_create("secondary")
    
    registry.set_fallback_order("primary", ["secondary"])
    
    # Both active -> should pick preferred
    assert registry.get_available_provider("primary") == "primary"
    
    # Trip primary
    cb_primary.record_failure()
    cb_primary.record_failure()
    cb_primary.record_failure()
    cb_primary.record_failure()
    cb_primary.record_failure()
    assert cb_primary.state == CircuitState.OPEN
    
    # Should fallback to secondary
    assert registry.get_available_provider("primary") == "secondary"
    
    # Trip secondary too
    cb_secondary.record_failure()
    cb_secondary.record_failure()
    cb_secondary.record_failure()
    cb_secondary.record_failure()
    cb_secondary.record_failure()
    
    # None available
    assert registry.get_available_provider("primary") is None


# ── Rate Limiter Tests ───────────────────────────────────────────────────────

def test_sliding_window_counter():
    counter = SlidingWindowCounter(window_seconds=0.1)
    assert counter.count == 0
    
    counter.record()
    counter.record()
    assert counter.count == 2
    
    time.sleep(0.12)
    assert counter.count == 0


def test_rate_limiter_categories_and_rules():
    limiter = RateLimiter()
    
    # Default category for paths
    assert limiter._classify_endpoint("/api/chat/send") == "chat"
    assert limiter._classify_endpoint("/api/completions") == "completion"
    assert limiter._classify_endpoint("/api/tools/list") == "tools"
    assert limiter._classify_endpoint("/api/files/open") == "files"
    assert limiter._classify_endpoint("/api/other") == "default"
    
    # Tier-based limit retrieval
    assert limiter._get_limit("free", "chat") == 20
    assert limiter._get_limit("pro", "chat") == 60
    assert limiter._get_limit("enterprise", "chat") == 300
    
    # Basic checking
    resp = limiter.check("tenant_1", "user_1", "/api/chat", tier="free")
    assert resp.result == RateLimitResult.ALLOWED
    assert resp.limit == 20
    
    # Exceed limit
    limiter.reset()
    for _ in range(20):
        limiter.check("tenant_1", "user_1", "/api/chat", tier="free")
        
    resp_limit_hit = limiter.check("tenant_1", "user_1", "/api/chat", tier="free")
    assert resp_limit_hit.result == RateLimitResult.THROTTLED
    assert resp_limit_hit.retry_after > 0.0
    
    # Test custom rules and burst
    limiter.reset()
    rule = RateLimitRule(endpoint_pattern="/api/special", requests_per_minute=2, burst_size=1, cooldown_seconds=0.5)
    limiter.add_rule(rule)
    
    # Base limit is 100 for default category. With multiplier=0.01, effective limit is max(1, 100*0.01) = 1.
    # Total limit = 1 + burst (1) = 2.
    assert limiter.check("t1", "u1", "/api/special", multiplier=0.01).result == RateLimitResult.ALLOWED
    assert limiter.check("t1", "u1", "/api/special", multiplier=0.01).result == RateLimitResult.ALLOWED
    
    # 3rd should be throttled
    resp_cooldown = limiter.check("t1", "u1", "/api/special", multiplier=0.01)
    assert resp_cooldown.result == RateLimitResult.THROTTLED
    assert resp_cooldown.retry_after >= 0.5

    
    # Check stats
    stats = limiter.get_stats()
    assert stats["active_windows"] > 0


# ── Session Manager Tests ────────────────────────────────────────────────────

def test_session_lifecycle():
    manager = GatewaySessionManager(session_ttl=0.2, max_sessions_per_user=3)
    
    # Create sessions
    s1 = manager.create_session("tenant_1", "user_1", "/root/workspace", "gpt-4")
    assert s1.session_id.startswith("sess-")
    assert s1.state == SessionState.CREATED
    assert s1.is_alive is True
    
    # Activate
    manager.activate_session(s1.session_id)
    assert s1.state == SessionState.ACTIVE
    
    # Pause and resume
    manager.pause_session(s1.session_id)
    assert s1.state == SessionState.PAUSED
    manager.resume_session(s1.session_id)
    assert s1.state == SessionState.ACTIVE
    
    # Max sessions auto-eviction (enforces max_sessions_per_user=3)
    s2 = manager.create_session("tenant_1", "user_1")
    s3 = manager.create_session("tenant_1", "user_1")
    
    assert len(manager.get_user_sessions("user_1", alive_only=True)) == 3
    
    # 4th session creation should terminate s1 (oldest)
    s4 = manager.create_session("tenant_1", "user_1")
    assert len(manager.get_user_sessions("user_1", alive_only=True)) == 3
    assert manager.get_session(s1.session_id).state == SessionState.TERMINATED
    
    # Session TTL expiry
    time.sleep(0.22)
    # Accessing session via get_session checks TTL
    assert manager.get_session(s2.session_id).state == SessionState.EXPIRED
    
    # Cleanup expired
    cleaned_count = manager.cleanup_expired()
    assert cleaned_count >= 0


# ── Streaming Manager Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_channel_and_manager():
    manager = StreamManager()
    
    # Create channel
    config = StreamConfig(buffer_size=5, backpressure_threshold=3, heartbeat_interval=0.1)
    ch = manager.create_channel(channel_id="my_stream", config=config)
    
    assert ch.channel_id == "my_stream"
    assert ch.state == StreamState.CREATED
    
    # Start stream
    ch.start()
    assert ch.state == StreamState.ACTIVE
    
    # Listeners
    pushed_messages = []
    ch.add_listener(lambda m: pushed_messages.append(m))
    
    # Push messages (first 2)
    ch.push("chunk", "hello")
    ch.push("chunk", "world")
    
    assert len(pushed_messages) == 2
    assert pushed_messages[0].data == "hello"
    
    # Push 3rd message to trigger backpressure (backpressure threshold = 3)
    flow_ok = ch.push("chunk", "!")
    assert flow_ok is False
    assert ch.is_backpressured is True
    
    # Consume messages using iterator
    # We run consumer in task
    consumed = []
    async def run_consumer():
        async for msg in ch.consume():
            consumed.append(msg)
            if len(consumed) == 3:
                break
                
    await asyncio.wait_for(run_consumer(), timeout=1.0)
    assert len(consumed) == 3
    assert consumed[0].data == "hello"
    assert consumed[1].data == "world"
    assert consumed[2].data == "!"
    
    # Heartbeat timeout check
    # consume runs again and since buffer is empty, should generate a heartbeat
    heartbeats = []
    async def get_heartbeat():
        async for msg in ch.consume():
            if msg.event_type == "heartbeat":
                heartbeats.append(msg)
                break
    
    await asyncio.wait_for(get_heartbeat(), timeout=0.5)
    assert len(heartbeats) == 1
    
    # Stats
    stats = ch.get_stats()
    assert stats["total_messages"] == 3
    
    # Close channel
    manager.close_channel("my_stream")
    assert ch.state == StreamState.COMPLETED
    assert manager.get_channel("my_stream") is None


@pytest.mark.asyncio
async def test_apply_patch_custom_format(tmp_path):
    from backend.app.tools.patch_tool import apply_patch
    
    class MockSession:
        workspace_root = str(tmp_path)
        pending_confirmations = {}
        async def send_ws_message(self, msg):
            pass
            
    session = MockSession()
    custom_patch = (
        "*** Begin Patch\n"
        "*** Add File: test_file.txt\n"
        "+Hello World!\n"
        "+This is a custom patch format.\n"
        "*** End Patch"
    )
    
    res = await apply_patch(session, "tc_123", {"patch": custom_patch}, auto_apply=True)
    assert "Patched test_file.txt" in res
    
    file_path = tmp_path / "test_file.txt"
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "Hello World!" in content
    assert "This is a custom patch format." in content

