class AgentSystemError(Exception):
    """Base exception for all errors in the parallel agent system."""
    pass


class AgentError(AgentSystemError):
    """Base exception raised for runtime errors during agent execution."""
    pass


class BudgetExceeded(AgentError):
    """Exception raised when an agent or global execution exceeds its budget constraints."""
    pass


class StuckError(AgentError):
    """Exception raised when an agent execution is detected to be stuck or looping."""
    pass
