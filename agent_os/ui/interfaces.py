from abc import ABC, abstractmethod
from typing import Any, Dict

class IAgentUX(ABC):
    """Layout manager displaying plan indicators, action steps, tool outputs, and cost metrics."""
    @abstractmethod
    def render_plan(self, plan: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def render_tool_execution(self, name: str, state: str) -> None:
        pass


class IUserInterface(ABC):
    """Native OS shell user interface hooks."""
    @abstractmethod
    def prompt_confirmation(self, message: str) -> bool:
        pass

    @abstractmethod
    def show_notification(self, title: str, text: str) -> None:
        pass
