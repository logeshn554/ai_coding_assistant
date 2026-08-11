from typing import Any, Dict, List
import concurrent.futures
from collections import defaultdict
from agent_os.skills.interfaces import ISkill, ISkillScheduler

class SkillScheduler(ISkillScheduler):
    """Skill Scheduler orchestrating skill execution based on Task State mappings, priority, and parallelism."""
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
        # Sort skills by priority (highest first)
        skills.sort(key=lambda s: getattr(s, "priority", 0), reverse=True)
        
        # Group skills by priority levels
        groups = defaultdict(list)
        for s in skills:
            groups[getattr(s, "priority", 0)].append(s)
            
        sorted_priorities = sorted(groups.keys(), reverse=True)
        
        for priority in sorted_priorities:
            group_skills = groups[priority]
            if len(group_skills) == 1:
                context = group_skills[0].execute(context)
            else:
                # Run matching same-priority skills in parallel
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(s.execute, dict(context)) for s in group_skills]
                    results = [f.result() for f in futures]
                    # Merge execution logs and dictionary outputs
                    for res in results:
                        for k, v in res.items():
                            if k == "logs" and isinstance(v, list):
                                existing_logs = context.get("logs", [])
                                context["logs"] = existing_logs + [log for log in v if log not in existing_logs]
                            else:
                                context[k] = v
        return context
