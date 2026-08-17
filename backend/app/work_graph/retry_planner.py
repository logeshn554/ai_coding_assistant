"""
Retry Planner — Configurable retry strategy helper for failed agent tasks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("loopix.work_graph.retry_planner")


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_factor: float = 1.5
    alternative_agent_type: Optional[str] = None


class RetryPlanner:
    """Calculates backoffs and redirects failed tasks to alternative agent types or settings."""

    def __init__(self) -> None:
        self._task_attempts: dict[str, int] = {}
        self._policies: dict[str, RetryPolicy] = {
            "code": RetryPolicy(max_retries=2, alternative_agent_type="debug"),
            "test": RetryPolicy(max_retries=3, backoff_factor=1.0),
            "review": RetryPolicy(max_retries=1),
        }

    def register_failure(self, task_id: str, agent_type: str) -> bool:
        """Register a failure and check if a retry is allowed.

        Returns True if a retry should be scheduled, False if max retries exceeded.
        """
        attempts = self._task_attempts.get(task_id, 0) + 1
        self._task_attempts[task_id] = attempts

        policy = self._policies.get(agent_type, RetryPolicy())
        
        if attempts <= policy.max_retries:
            logger.info(
                f"Retry recommended for task '{task_id}' (attempt {attempts}/{policy.max_retries} "
                f"for agent '{agent_type}')"
            )
            return True

        logger.warning(f"Max retries exceeded for task '{task_id}'. Escalating failure.")
        return False

    def get_backoff(self, task_id: str, agent_type: str) -> float:
        attempts = self._task_attempts.get(task_id, 0)
        policy = self._policies.get(agent_type, RetryPolicy())
        return policy.backoff_factor ** attempts

    def get_alternative_agent(self, agent_type: str) -> Optional[str]:
        policy = self._policies.get(agent_type, RetryPolicy())
        return policy.alternative_agent_type


# ── Singleton ───────────────────────────────────────────────────────────────

retry_planner = RetryPlanner()
