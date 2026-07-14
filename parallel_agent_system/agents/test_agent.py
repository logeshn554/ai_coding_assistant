from parallel_agent_system.agents.base import BaseParallelAgent


class TestAgent(BaseParallelAgent):
    """
    TestAgent responsible for writing pytest tests, executing tests,
    fixing test errors, and verifying test suite coverage.
    """
    agent_type = "test"
    default_tools = ["bash", "file_editor", "ipython"]
