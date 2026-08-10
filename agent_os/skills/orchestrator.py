import copy
import asyncio
from typing import Any, Dict, List
from agent_os.skills.interfaces import ISkill
from agent_os.skills.plugins import IDEContext

class SkillOrchestrator:
    """SkillOrchestrator handling parallel & pipeline skill execution with deep-copied contexts."""
    def __init__(self) -> None:
        self._skills: Dict[str, ISkill] = {}

    def register_skill(self, name: str, skill: ISkill) -> None:
        self._skills[name.lower()] = skill

    def get_skill(self, name: str) -> ISkill | None:
        name_lower = name.lower()
        if name_lower in self._skills:
            return self._skills[name_lower]
        # Heuristic lookup to match clean names (e.g. rename_symbol -> renamesymbol)
        clean_name = name_lower.replace("_", "").replace(" ", "")
        for k, v in self._skills.items():
            k_clean = k.replace("_", "").replace(" ", "")
            if k_clean == clean_name or v.__class__.__name__.lower().replace("skill", "") == clean_name:
                return v
        return None

    async def run_parallel(self, skill_names: List[str], context: IDEContext) -> IDEContext:
        skills_to_run = []
        for name in skill_names:
            s = self.get_skill(name)
            if s is None:
                raise ValueError(f"Skill '{name}' not found in registry.")
            skills_to_run.append(s)

        if not skills_to_run:
            return context

        loop = asyncio.get_running_loop()

        def _execute_skill(skill: ISkill, ctx_copy: IDEContext) -> Dict[str, Any]:
            return skill.execute(ctx_copy)

        futures = []
        for s in skills_to_run:
            # Deep copy to maintain parallelism state isolation
            ctx_copy = copy.deepcopy(context)
            futures.append(loop.run_in_executor(None, _execute_skill, s, ctx_copy))

        results = await asyncio.gather(*futures)

        # Merge results back into the original context
        for res in results:
            for k, v in res.items():
                if k == "logs" and isinstance(v, list):
                    for log in v:
                        if log not in context.logs:
                            context.logs.append(log)
                else:
                    context[k] = v

        return context

    async def run_pipeline(self, skill_names: List[str], context: IDEContext) -> IDEContext:
        loop = asyncio.get_running_loop()
        for name in skill_names:
            s = self.get_skill(name)
            if s is None:
                raise ValueError(f"Skill '{name}' not found in registry.")
            context = await loop.run_in_executor(None, s.execute, context)
        return context
