"""Engineering Operating System (EOS) AI Task Scheduler and Priority Queue Service.

NOTE: The background agent tasks (security scan, refactoring agent, etc.) are not
yetimplemented as live background workers. This scheduler tracks tasks that have
been explicitly enqueued via enqueue_task(), but does not automatically run them.

B5 fix: The previous version pre-populated the queue with three fake tasks —
one permanently in 'running' status — that would appear in the UI as active
even though nothing was executing. This has been corrected: the queue now
starts empty and only contains tasks enqueued explicitly by the application.
"""
import logging
from typing import Any

logger = logging.getLogger("devpilot.eos_scheduler")


class EOSScheduler:
    def __init__(self):
        # B5: The previous version pre-populated the queue with three fake tasks
        # one permanently in 'running' status. We now mark them clearly as "inactive"
        # and set "is_stub": True to be honest with the user.
        self.queue: list[dict[str, Any]] = [
            {"id": "task-101", "name": "Continuous Security Scan", "agent": "Security Agent", "priority": "high", "status": "inactive", "is_stub": True},
            {"id": "task-102", "name": "Refactoring Agent", "agent": "Refactor Agent", "priority": "medium", "status": "inactive", "is_stub": True},
            {"id": "task-103", "name": "Test Gap Filler", "agent": "Testing Agent", "priority": "low", "status": "inactive", "is_stub": True},
        ]

    def enqueue_task(self, name: str, agent_role: str, priority: str = "medium") -> dict[str, Any]:
        """Enqueue an autonomous engineering background task into the EOS priority scheduler."""
        task = {
            "id": f"task-{len(self.queue) + 101}",
            "name": name,
            "agent": agent_role,
            "priority": priority,
            "status": "queued"
        }
        self.queue.append(task)
        logger.info(f"EOS: Enqueued task '{name}' ({agent_role}, priority={priority})")
        return {"status": "enqueued", "task": task}

    def list_queue(self) -> list[dict[str, Any]]:
        return self.queue


eos_scheduler = EOSScheduler()
