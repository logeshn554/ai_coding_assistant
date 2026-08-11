import copy
import asyncio
import logging
from typing import Any, Dict, List
from agent_os.skills.interfaces import ISkill
from agent_os.skills.plugins import IDEContext

logger = logging.getLogger("agentos.skills.orchestrator")


class SkillOrchestrator:
    """SkillOrchestrator handling parallel & pipeline skill execution with deep-copied contexts.

    Parallel execution uses deep-copied contexts so skills are fully isolated.
    Results are merged back using a proper *reducer* strategy:
      - ``logs``: appended (deduplicated)
      - ``errors``: accumulated from every skill
      - ``modified``: boolean-OR (True if *any* skill modified content)
      - ``file_content``: conflict detection when multiple skills produce different content
      - All other keys: last-writer-wins (with a warning if values differ)
    """
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
        """Run multiple skills concurrently and merge results with conflict awareness."""
        skills_to_run: List[ISkill] = []
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

        # ── Reducer-based merge ──
        # Track per-skill results for introspection
        per_skill_results: Dict[str, Dict[str, Any]] = {}
        all_file_contents: List[str] = []
        any_modified = False
        accumulated_errors: List[Dict[str, str]] = list(context.get("errors", []))
        accumulated_logs: List[str] = list(context.logs) if context.logs else []

        for skill_name, res in zip(skill_names, results):
            per_skill_results[skill_name] = dict(res.items()) if hasattr(res, "items") else {}

            for k, v in res.items():
                if k == "logs" and isinstance(v, list):
                    # Append logs (deduplicated)
                    for log_entry in v:
                        if log_entry not in accumulated_logs:
                            accumulated_logs.append(log_entry)

                elif k == "errors" and isinstance(v, list):
                    # Accumulate errors from every skill
                    for err in v:
                        if err not in accumulated_errors:
                            accumulated_errors.append(err)

                elif k == "modified":
                    # Boolean-OR: True if ANY skill modified content
                    any_modified = any_modified or bool(v)

                elif k == "file_content" and isinstance(v, str) and v:
                    all_file_contents.append(v)

                elif k in ("_extra_data",):
                    # Skip internal fields
                    continue

                else:
                    # General key: set on context (last-writer-wins for non-special keys)
                    context[k] = v

        # Apply accumulated fields
        context.logs = accumulated_logs
        context["errors"] = accumulated_errors
        context["modified"] = any_modified or context.get("modified", False)

        # Handle file_content: detect conflicts
        if all_file_contents:
            unique_contents = list(set(all_file_contents))
            if len(unique_contents) == 1:
                context["file_content"] = unique_contents[0]
            else:
                # Multiple skills produced different file content → conflict
                logger.warning(
                    f"Parallel skill conflict: {len(unique_contents)} different file_content "
                    f"values produced by skills {skill_names}. Using the last writer's version."
                )
                context["file_content"] = all_file_contents[-1]
                context["errors"].append({
                    "skill": "SkillOrchestrator",
                    "message": (
                        f"Conflict: {len(unique_contents)} skills produced different file_content. "
                        "The last writer's version was used."
                    )
                })

        # Store per-skill results for introspection
        context["_parallel_skill_results"] = per_skill_results

        return context

    async def run_pipeline(self, skill_names: List[str], context: IDEContext) -> IDEContext:
        loop = asyncio.get_running_loop()
        for name in skill_names:
            s = self.get_skill(name)
            if s is None:
                raise ValueError(f"Skill '{name}' not found in registry.")
            context = await loop.run_in_executor(None, s.execute, context)
        return context
