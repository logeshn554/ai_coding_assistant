import os
import sys
import warnings

# DEPRECATED: Scheduled for removal in sprint 2. Use backend.app.agent.agent_runtime instead.
warnings.warn(
    "parallel_agent_system is deprecated and scheduled for removal in sprint 2. Use backend.app.agent.agent_runtime instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Prevent mock libraries (like local 'langgraph' stub in the workspace root) from hijacking imports
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else ""

workspace_root_norm = norm(workspace_root)

# Filter sys.path to remove workspace root
sys.path = [p for p in sys.path if p and p != "." and norm(p) != workspace_root_norm]


