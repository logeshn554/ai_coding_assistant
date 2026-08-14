from parallel_agent_system.agents.base import BaseParallelAgent


class FrontendAgent(BaseParallelAgent):
    agent_type = "frontend"
    default_tools = ["bash", "file_editor", "task_tracker"]


class BackendAgent(BaseParallelAgent):
    agent_type = "backend"
    default_tools = ["bash", "file_editor", "ipython", "task_tracker"]


class SecurityAgent(BaseParallelAgent):
    agent_type = "security"
    default_tools = ["bash", "file_editor", "task_tracker"]


class PerformanceAgent(BaseParallelAgent):
    agent_type = "performance"
    default_tools = ["bash", "file_editor", "ipython", "task_tracker"]


class DebugAgent(BaseParallelAgent):
    agent_type = "debug"
    default_tools = ["bash", "file_editor", "ipython", "task_tracker"]


class DatabaseAgent(BaseParallelAgent):
    agent_type = "database"
    default_tools = ["bash", "file_editor", "task_tracker"]


class ApiAgent(BaseParallelAgent):
    agent_type = "api"
    default_tools = ["bash", "file_editor", "task_tracker"]


class IntegrationAgent(BaseParallelAgent):
    agent_type = "integration"
    default_tools = ["bash", "file_editor", "task_tracker"]


class DevOpsAgent(BaseParallelAgent):
    agent_type = "devops"
    default_tools = ["bash", "file_editor", "task_tracker"]


class ReleaseAgent(BaseParallelAgent):
    agent_type = "release"
    default_tools = ["bash", "file_editor", "task_tracker"]


class GitAgent(BaseParallelAgent):
    agent_type = "git"
    default_tools = ["bash", "file_editor", "task_tracker"]


class TerminalAgent(BaseParallelAgent):
    agent_type = "terminal"
    default_tools = ["bash", "task_tracker"]


class PlannerAgent(BaseParallelAgent):
    agent_type = "planner"
    default_tools = ["file_editor", "task_tracker"]


class ArchitectAgent(BaseParallelAgent):
    agent_type = "architect"
    default_tools = ["file_editor", "task_tracker"]


class RequirementAgent(BaseParallelAgent):
    agent_type = "requirement"
    default_tools = ["file_editor", "task_tracker"]
