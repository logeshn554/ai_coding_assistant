from typing import Any, Dict, List
from agent_os.skills.interfaces import ISkill, ISkillScheduler

class SkillScheduler(ISkillScheduler):
    """Skill Scheduler orchestrating skill execution based on Task State mappings."""
    def __init__(self) -> None:
        self._registry: Dict[str, List[ISkill]] = {}

    def register_skill(self, state: str, skill: ISkill) -> None:
        state_key = state.upper()
        if state_key not in self._registry:
            self._registry[state_key] = []
        self._registry[state_key].append(skill)

    def get_skills_for_state(self, state: str) -> List[ISkill]:
        return self._registry.get(state.upper(), [])

    def schedule_skills(self, state: str, context: Dict[str, Any]) -> Dict[str, Any]:
        skills = self.get_skills_for_state(state)
        # Execute each matching skill sequentially and update context
        for skill in skills:
            context = skill.execute(context)
        return context
