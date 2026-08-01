from parallel_agent_system.agents.base import BaseParallelAgent


class ReviewAgent(BaseParallelAgent):
    """
    ReviewAgent responsible for running code checks (ruff, mypy, bandit),
    remediation of lint findings, and reporting security risks for human verification.
    """
    agent_type = "review"
    default_tools = ["bash", "file_editor"]
