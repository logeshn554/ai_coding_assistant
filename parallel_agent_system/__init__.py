import os
import sys

# Prevent mock libraries (like local 'langgraph' stub in the workspace root) from hijacking imports
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else ""

workspace_root_norm = norm(workspace_root)

# Filter sys.path to remove workspace root
sys.path = [p for p in sys.path if p and p != "." and norm(p) != workspace_root_norm]

