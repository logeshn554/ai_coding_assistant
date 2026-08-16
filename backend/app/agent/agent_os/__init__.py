# AgentOS Package (DEPRECATED: Use backend.app.agent.agent_runtime instead)
import warnings
warnings.warn(
    "agent_os is deprecated and scheduled for removal in sprint 2. Use backend.app.agent.agent_runtime instead.",
    DeprecationWarning,
    stacklevel=2,
)

__version__ = "0.2.0"

try:
    from agent_os.agent_os import AgentOS
    __all__ = ["AgentOS"]
except ImportError:
    __all__ = []

