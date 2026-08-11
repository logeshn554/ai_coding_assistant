from parallel_agent_system.agents.base import BaseParallelAgent


class DocsAgent(BaseParallelAgent):
    """
    DocsAgent responsible for docstrings, README files, and CHANGELOG maintenance.
    Must never modify source code functional logic.
    """
    agent_type = "docs"
    default_tools = ["file_editor", "bash"]
