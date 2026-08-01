"""
Integration test for collaboration log token footprint optimization.
Verifies that the collaboration log size plateaus to save context window tokens.
"""

import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest
from unittest.mock import MagicMock, patch
from backend.app.orchestrator import maybe_summarise_log


@pytest.mark.asyncio
async def test_log_summarisation_token_plateau():
    """Verify that log size plateaus and does not grow linearly after summarization."""
    mock_session = MagicMock()
    mock_session.profile = {}
    mock_session.collaboration_log = []

    # Mock the LLM router completion call to return a fixed 100-word summary string
    mock_summary_text = (
        "Summary of previous tasks: " + " ".join(["word"] * 100) + "."
    )

    state = {
        "collaboration_log": [],
        "session": mock_session,
    }

    # Simulate 15 turns, each adding a ~200 character log entry
    synthetic_entry = "Turn log detail: " + "x" * 180

    before_sizes = []
    after_sizes = []

    for turn in range(1, 16):
        state["collaboration_log"].append(synthetic_entry)
        
        # Calculate size before summarization
        before_size = len(json.dumps(state["collaboration_log"]))
        before_sizes.append(before_size)
        
        # Call maybe_summarise_log
        with patch("backend.app.adapters.router.ModelRouter.completion", return_value=mock_summary_text):
            state = await maybe_summarise_log(state, mock_session)
            
        # Calculate size after summarization
        after_size = len(json.dumps(state["collaboration_log"]))
        after_sizes.append(after_size)

    # Print sizes for CI log visibility
    print("\nLog size progression:")
    for turn in range(15):
        print(f"Turn {turn+1:02d}: Before={before_sizes[turn]:5d} bytes | After={after_sizes[turn]:5d} bytes")

    # Assert that token plateau holds: final size must be under 6000 characters
    final_size = len(json.dumps(state["collaboration_log"]))
    assert final_size < 6000
    
    # Confirm that compression actually took place (final log size after compression grew to 10 at turn 15)
    assert len(state["collaboration_log"]) == 10
