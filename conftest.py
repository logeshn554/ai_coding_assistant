# Pytest configuration to ignore binary test result file that causes UnicodeDecodeError during collection.
collect_ignore = ["frontend/test_results.txt", "frontend/test_out.txt", "frontend/test_run.txt", "test.txt", "test_temp.txt", "testfile_from_agent.txt"]

import os
import sys

# Prevent broken native precompiled modules from crashing collection
sys.modules["transformers"] = None
sys.modules["torch"] = None
sys.modules["sympy"] = None

# Set DEVPILOT_TEST_MODE for backend test stub imports
os.environ["DEVPILOT_TEST_MODE"] = "1"
# Disable HTTP token auth in the test environment so TestClient calls don't
# need to supply a bearer token. Auth is tested at the WS level with the
# S1 fix. HTTP-level auth (verify_token) is a deployment concern.
os.environ.setdefault("DEVPILOT_NO_AUTH", "true")
