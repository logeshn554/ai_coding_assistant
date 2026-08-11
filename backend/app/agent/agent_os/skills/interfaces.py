from abc import ABC, abstractmethod
from typing import Any, List, Dict

class ISkillRegistry(ABC):
    """Registry managing available specialist skills and tool descriptions."""
    @abstractmethod
    def register_skill(self, name: str, description: str, definition: Any) -> None:
        pass

    @abstractmethod
    def get_skill(self, name: str) -> Any:
        pass


class ISkillManager(ABC):
    """Dynamic resolution and verification of specialist tools."""
    @abstractmethod
    def match_skills(self, task_description: str) -> List[str]:
        pass


class ISkill(ABC):
    """Specialist Skill plugin abstraction."""
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass


class ISkillScheduler(ABC):
    """Scheduler selecting and executing skills based on task states."""
    @abstractmethod
    def register_skill(self, state: str, skill: ISkill) -> None:
        pass

    @abstractmethod
    def get_skills_for_state(self, state: str) -> List[ISkill]:
        pass

    @abstractmethod
    def schedule_skills(self, state: str, context: Dict[str, Any]) -> Dict[str, Any]:
        pass
