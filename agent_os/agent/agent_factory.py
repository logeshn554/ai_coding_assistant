"""
Agent factory for creating agents with proper configuration.

Handles agent instantiation, tool registry wiring, and agent type routing.
"""

from typing import Dict, Optional
from .interfaces import IAgent, IAgentFactory, ToolDefinition
from .base_agent import BaseAgent
from .tool_registry import ToolRegistry


class AgentFactory(IAgentFactory):
    """Creates agents with proper tool registry and configuration."""

    def __init__(self, model_router, tool_registry: Optional[ToolRegistry] = None):
        """
        Args:
            model_router: LLM model router for agent LLM calls
            tool_registry: Tool registry (creates default if not provided)
        """
        self.model_router = model_router
        self.tool_registry = tool_registry or ToolRegistry()

        # Agent type to specialized tools mapping
        self._agent_type_tools = {
            "coding": self._get_coding_tools(),
            "testing": self._get_testing_tools(),
            "review": self._get_review_tools(),
            "analysis": self._get_analysis_tools(),
            "refactor": self._get_refactor_tools(),
        }

    async def create_agent(self, agent_type: str) -> IAgent:
        """
        Create an agent of the given type.

        Args:
            agent_type: Type of agent (coding, testing, review, etc.)

        Returns:
            Configured agent instance

        Raises:
            ValueError if agent_type is not supported
        """
        if agent_type not in self._agent_type_tools:
            supported = ", ".join(self.get_supported_types())
            raise ValueError(
                f"Unsupported agent type: {agent_type}. Supported: {supported}"
            )

        # Get tools for this agent type
        tools = self._agent_type_tools[agent_type]

        # Create agent with filtered tool registry
        import uuid
        agent_id = f"agent-{agent_type}-{str(uuid.uuid4())[:8]}"

        agent = BaseAgent(
            agent_id=agent_id,
            agent_type=agent_type,
            model_router=self.model_router,
            tools_registry=tools,
        )

        return agent

    def get_supported_types(self) -> list[str]:
        """Return list of supported agent types."""
        return list(self._agent_type_tools.keys())

    def get_tools_for_type(self, agent_type: str) -> Dict[str, ToolDefinition]:
        """Get tools available for an agent type."""
        return self._agent_type_tools.get(agent_type, {})

    def _get_coding_tools(self) -> Dict[str, ToolDefinition]:
        """Tools for coding agent."""
        tool_names = [
            "read_file",
            "write_file",
            "create_file",
            "edit_file",
            "delete_file",
            "rename_file",
            "list_directory",
            "search_text",
            "search_files",
            "run_terminal_command",
            "run_linter",
            "run_typecheck",
            "git_status",
            "git_diff",
            "git_log",
        ]
        return self._get_tools_by_names(tool_names)

    def _get_testing_tools(self) -> Dict[str, ToolDefinition]:
        """Tools for testing agent."""
        tool_names = [
            "read_file",
            "write_file",
            "create_file",
            "edit_file",
            "list_directory",
            "search_text",
            "run_tests",
            "run_linter",
            "run_typecheck",
            "run_build",
            "run_terminal_command",
            "git_status",
            "git_diff",
        ]
        return self._get_tools_by_names(tool_names)

    def _get_review_tools(self) -> Dict[str, ToolDefinition]:
        """Tools for review agent."""
        tool_names = [
            "read_file",
            "list_directory",
            "search_text",
            "git_diff",
            "git_log",
            "run_linter",
            "run_typecheck",
            "search_files",
        ]
        return self._get_tools_by_names(tool_names)

    def _get_analysis_tools(self) -> Dict[str, ToolDefinition]:
        """Tools for analysis agent."""
        tool_names = [
            "read_file",
            "list_directory",
            "search_text",
            "search_files",
            "git_log",
            "git_status",
            "run_terminal_command",
        ]
        return self._get_tools_by_names(tool_names)

    def _get_refactor_tools(self) -> Dict[str, ToolDefinition]:
        """Tools for refactoring agent."""
        tool_names = [
            "read_file",
            "write_file",
            "edit_file",
            "delete_file",
            "rename_file",
            "list_directory",
            "search_text",
            "search_files",
            "run_linter",
            "run_typecheck",
            "run_tests",
            "git_status",
            "git_diff",
            "run_terminal_command",
        ]
        return self._get_tools_by_names(tool_names)

    def _get_tools_by_names(self, names: list[str]) -> Dict[str, ToolDefinition]:
        """Get tools by name list."""
        tools = {}
        all_tools = self.tool_registry.get_all()
        for name in names:
            if name in all_tools:
                tools[name] = all_tools[name]
        return tools
