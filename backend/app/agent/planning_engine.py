"""Phase 2 — Planning Engine.

For non-trivial tasks, generates a structured, dependency-ordered
task graph before execution begins.

The plan is injected into the LLM context so the agent executes
step-by-step instead of in one monolithic prompt.

Plan format:
  {
    "goal": "...",
    "steps": [
      {"id": 1, "task": "...", "type": "context", "deps": [], "status": "pending"},
      {"id": 2, "task": "...", "type": "create",  "deps": [1], "status": "pending"},
      ...
    ]
  }

Step types: context, create, implement, test, validate, search, explain
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .intent_router import IntentType

logger = logging.getLogger("devpilot.agent.planning_engine")


@dataclass
class Plan:
    goal: str
    steps: list[dict]  # Each: {id, task, type, deps, status}

    def to_prompt_block(self) -> str:
        if not self.steps:
            return ""
        lines = [
            "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "EXECUTION PLAN (follow this order — do not skip steps)",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Goal: {self.goal}",
            "",
        ]
        for s in self.steps:
            dep_str = f" [after steps {s['deps']}]" if s.get("deps") else ""
            lines.append(f"  Step {s['id']}: {s['task']}{dep_str}")
        lines.append("")
        lines.append("Complete every step in order. Mark each step done before proceeding.")
        return "\n".join(lines)


class PlanningEngine:
    """Generate a step-by-step task graph for a given user request.

    For simple/trivial requests, returns an empty plan (agent runs freely).
    For complex requests, generates an ordered step list with dependencies.
    """

    def generate(
        self,
        goal: str,
        intent: IntentType,
        referenced_files: list[str],
        spec_file: str | None,
        workspace_has_files: bool,
    ) -> Plan:
        """Generate a task plan.

        Args:
            goal: The user's request.
            intent: Classified intent type.
            referenced_files: Files mentioned in the query.
            spec_file: Spec document if IMPLEMENT_SPEC intent.
            workspace_has_files: Whether the workspace is non-empty.

        Returns:
            A Plan with ordered steps (may be empty for trivial tasks).
        """
        steps: list[dict] = []

        if intent == IntentType.IMPLEMENT_SPEC:
            steps = self._plan_implement_spec(goal, spec_file, referenced_files)

        elif intent == IntentType.BUG_FIX:
            steps = self._plan_bug_fix(goal, referenced_files)

        elif intent == IntentType.NEW_PROJECT:
            steps = self._plan_new_project(goal, workspace_has_files)

        elif intent == IntentType.REFACTOR:
            steps = self._plan_refactor(goal, referenced_files)

        elif intent == IntentType.REVIEW:
            steps = self._plan_review(goal, referenced_files)

        # EXPLAIN, SEARCH, CONTINUE, GENERAL: no plan needed — let agent run freely
        else:
            return Plan(goal=goal, steps=[])

        return Plan(goal=goal, steps=steps)

    # ── Per-intent plan templates ────────────────────────────────────────

    def _plan_implement_spec(
        self, goal: str, spec_file: str | None, refs: list[str]
    ) -> list[dict]:
        steps = []
        sid = 1

        if spec_file:
            steps.append({"id": sid, "task": f"Read and fully understand '{spec_file}'", "type": "context", "deps": [], "status": "pending"})
            sid += 1

        steps.append({"id": sid, "task": "List workspace root to understand existing structure", "type": "context", "deps": [sid - 1] if spec_file else [], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Design the architecture: list all files to create and their responsibilities", "type": "create", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Create all files identified in the architecture step", "type": "implement", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Install required dependencies if any", "type": "implement", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Verify: re-read original spec and check every requirement is satisfied", "type": "validate", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Run any available tests or build command to confirm correctness", "type": "test", "deps": [sid - 1], "status": "pending"})

        return steps

    def _plan_bug_fix(self, goal: str, refs: list[str]) -> list[dict]:
        steps = []
        sid = 1

        if refs:
            steps.append({"id": sid, "task": f"Read the referenced file(s): {', '.join(refs[:3])}", "type": "context", "deps": [], "status": "pending"})
            sid += 1
        else:
            steps.append({"id": sid, "task": "Search the codebase for the error/bug pattern", "type": "search", "deps": [], "status": "pending"})
            sid += 1
            steps.append({"id": sid, "task": "Read the file(s) containing the bug", "type": "context", "deps": [sid - 1], "status": "pending"})
            sid += 1

        steps.append({"id": sid, "task": "Identify the root cause of the bug", "type": "context", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Apply the fix to the affected file(s)", "type": "implement", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Run tests or build to verify the fix works", "type": "test", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Verify no regressions were introduced", "type": "validate", "deps": [sid - 1], "status": "pending"})

        return steps

    def _plan_new_project(self, goal: str, workspace_has_files: bool) -> list[dict]:
        steps = []
        sid = 1

        steps.append({"id": sid, "task": "List workspace root to check if it's empty or has existing files", "type": "context", "deps": [], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Choose tech stack and scaffolding approach based on workspace state", "type": "context", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Create project structure: config files, entry points, directory layout", "type": "create", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Implement core application logic", "type": "implement", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Install dependencies and verify the project builds/runs", "type": "test", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Verify all requested features are present", "type": "validate", "deps": [sid - 1], "status": "pending"})

        return steps

    def _plan_refactor(self, goal: str, refs: list[str]) -> list[dict]:
        steps = []
        sid = 1

        if refs:
            steps.append({"id": sid, "task": f"Read all affected files: {', '.join(refs[:4])}", "type": "context", "deps": [], "status": "pending"})
        else:
            steps.append({"id": sid, "task": "Identify all files involved in this refactor", "type": "search", "deps": [], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Plan the refactoring changes: what moves where, what gets renamed", "type": "context", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Apply refactoring changes to all affected files", "type": "implement", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Update imports/references in files that depend on changed code", "type": "implement", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Run tests/build to verify nothing is broken", "type": "test", "deps": [sid - 1], "status": "pending"})

        return steps

    def _plan_review(self, goal: str, refs: list[str]) -> list[dict]:
        steps = []
        sid = 1

        if refs:
            steps.append({"id": sid, "task": f"Read files to review: {', '.join(refs[:4])}", "type": "context", "deps": [], "status": "pending"})
        else:
            steps.append({"id": sid, "task": "List workspace to identify key files for review", "type": "context", "deps": [], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Analyse code for bugs, security issues, performance issues, and code quality", "type": "context", "deps": [sid - 1], "status": "pending"})
        sid += 1

        steps.append({"id": sid, "task": "Write a structured review report with findings and recommendations", "type": "implement", "deps": [sid - 1], "status": "pending"})

        return steps
