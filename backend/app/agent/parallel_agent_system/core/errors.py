class AgentSystemError(Exception):
    """Base exception for all errors in the parallel agent system."""


class AgentError(AgentSystemError):
    """Base exception raised for runtime errors during agent execution."""


class BudgetExceeded(AgentError):
    """Exception raised when an agent or global execution exceeds its budget constraints."""


class StuckError(AgentError):
    """Exception raised when an agent execution is detected to be stuck or looping."""
