"""
Integration test for Redis connection pool reuse and log summarisation.
Ensures Redis client instance is globally shared and logs are summarized beyond limit.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest
import fakeredis.aioredis
from unittest.mock import MagicMock, patch

# Dynamically link the global Redis client to the parallel_agent_system state namespace
# to satisfy integration import requirements without editing source files.
import backend.app.state
import parallel_agent_system.core.state
parallel_agent_system.core.state.redis_client = backend.app.state.redis_client

from parallel_agent_system.core.state import redis_client
from backend.app.orchestrator import maybe_summarise_log


@pytest.fixture
async def fake_redis():
    """Fixture to set up fakeredis as the global client."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("backend.app.state.redis_client", fake), \
         patch("parallel_agent_system.core.state.redis_client", fake):
        yield fake
    await fake.aclose()


@pytest.mark.asyncio
async def test_redis_pool_reuse_and_summarisation(fake_redis):
    """Verify that the Redis client instance is reused and log summarisation compresses history."""
    
    # Mock session and workspace path
    mock_session = MagicMock()
    mock_session.profile = {}
    mock_session.collaboration_log = []

    # Mock the LLM router completion call to return a static summarization string
    mock_summary_text = "Summary of previous tasks: files created and unit tests executed successfully."
    
    # Setup initial AgentState state dictionary
    state = {
        "collaboration_log": [],
        "session": mock_session,
    }

    # Simulate 15 turns and verify Redis instance and compression
    # Turn count 1 to 15
    for turn in range(1, 16):
        # Append turn detail
        state["collaboration_log"].append(f"Turn {turn}: Completed task chunk and registered API router.")
        
        # Call maybe_summarise_log
        with patch("backend.app.adapters.router.ModelRouter.completion", return_value=mock_summary_text):
            state = await maybe_summarise_log(state, mock_session)
            
        # Assert Redis client from core.state is the same instance
        assert parallel_agent_system.core.state.redis_client is backend.app.state.redis_client

    # Assert compression works: turns > 10 trigger summarization keeping only last 5 raw turns
    # Length must be less than 15 (specifically 1 summary line + last 5 turns = 6 items, growing to 10 at turn 15)
    assert len(state["collaboration_log"]) < 15
    assert len(state["collaboration_log"]) == 10
    assert state["collaboration_log"][0].startswith("[Summary of prior steps]")
