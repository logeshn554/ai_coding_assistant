# Pytest configuration for parallel_agent_system tests.
import os
import sys

def norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else ""

workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
workspace_root_norm = norm(workspace_root)

# Filter sys.path to remove any occurrences of workspace_root
sys.path = [p for p in sys.path if norm(p) != workspace_root_norm]

# Append the workspace_root to the end of sys.path
sys.path.append(workspace_root)
