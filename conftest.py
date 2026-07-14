# Pytest configuration to ignore binary test result file that causes UnicodeDecodeError during collection.
collect_ignore = ["frontend/test_results.txt", "frontend/test_out.txt", "frontend/test_run.txt"]

import os
import sys

# When running parallel_agent_system tests, make sure real langgraph package takes precedence
# over the local mock langgraph folder in the root.
if any("parallel_agent_system" in arg for arg in sys.argv):
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    while workspace_root in sys.path:
        sys.path.remove(workspace_root)
    sys.path.append(workspace_root)