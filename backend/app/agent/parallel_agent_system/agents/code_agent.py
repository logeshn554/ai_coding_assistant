from parallel_agent_system.agents.base import BaseParallelAgent


class CodeAgent(BaseParallelAgent):
    """
    CodeAgent responsible for writing, refactoring, and implementing solution logic.
    Follows a strict 4-phase methodology: explore -> analyze -> implement -> verify.
    """
    agent_type = "code"
    default_tools = ["bash", "file_editor", "ipython", "task_tracker"]
