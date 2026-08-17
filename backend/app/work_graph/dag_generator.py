"""
DAG Generator — Decomposes high-level intent into a directed acyclic graph (DAG) of symbol-level tasks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..intelligence.intent_compiler import CompiledIntent

logger = logging.getLogger("loopix.work_graph.dag_generator")


@dataclass
class DagTask:
    task_id: str
    description: str
    agent_type: str                     # code | test | review | docs
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"             # pending | running | success | failed


class DagGenerator:
    """Generates task dependency graphs for multi-agent coordination."""

    def generate_dag(self, intent: CompiledIntent, roles: list[str]) -> list[DagTask]:
        """Decompose intent into sequential DagTasks based on required capabilities."""
        tasks: list[DagTask] = []
        
        # 1. Base implementation task
        tasks.append(
            DagTask(
                task_id="task_implement",
                description=f"Implement changes for goal: {intent.goal}",
                agent_type="code"
            )
        )

        # 2. Add verification if test role is present (dependent on implementation)
        if "test" in roles:
            tasks.append(
                DagTask(
                    task_id="task_verify",
                    description="Run unit and integration verification tests",
                    agent_type="test",
                    dependencies=["task_implement"]
                )
            )

        # 3. Add security scan if security role is present
        if "security" in roles:
            tasks.append(
                DagTask(
                    task_id="task_security",
                    description="Perform security vulnerability scan on modifications",
                    agent_type="security",
                    dependencies=["task_implement"]
                )
            )

        # 4. Add peer review (dependent on verification)
        if "review" in roles:
            deps = ["task_implement"]
            if "task_verify" in [t.task_id for t in tasks]:
                deps.append("task_verify")
            tasks.append(
                DagTask(
                    task_id="task_review",
                    description="Peer review code layout and style compliance",
                    agent_type="review",
                    dependencies=deps
                )
            )

        # 5. Add documentation (dependent on implementation)
        if "docs" in roles:
            tasks.append(
                DagTask(
                    task_id="task_docs",
                    description="Update README, docstrings, or architectural notes",
                    agent_type="docs",
                    dependencies=["task_implement"]
                )
            )

        logger.info(f"Generated task DAG with {len(tasks)} dependent tasks.")
        return tasks


# ── Singleton ───────────────────────────────────────────────────────────────

dag_generator = DagGenerator()
