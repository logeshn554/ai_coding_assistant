# Pytest configuration to ignore binary test result file that causes UnicodeDecodeError during collection.
collect_ignore = ["frontend/test_results.txt", "frontend/test_out.txt", "frontend/test_run.txt"]

import os
import sys

# Set DEVPILOT_TEST_MODE for backend test stub imports
os.environ["DEVPILOT_TEST_MODE"] = "1"

# When running parallel_agent_system tests, ensure real langgraph package takes precedence
if any("parallel_agent_system" in arg for arg in sys.argv):
    os.environ.pop("DEVPILOT_TEST_MODE", None)
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    while workspace_root in sys.path:
        sys.path.remove(workspace_root)
    sys.path.append(workspace_root)