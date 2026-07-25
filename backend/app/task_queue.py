"""
task_queue.py — Autonomous Agent Task Queue Manager for Antigravity.

Manages background AI agent task queues with support for priority, status tracking,
pause/resume, task re-ordering, retry, and cancellation across IDE sessions.
"""

import uuid
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("antigravity.tasks")


class TaskItem:
    def __init__(self, title: str, mode: str = "Agent", priority: str = "medium"):
        self.id = f"task_{uuid.uuid4().hex[:8]}"
        self.title = title
        self.mode = mode
        self.priority = priority  # 'high', 'medium', 'low'
        self.status = "queued"     # 'queued', 'running', 'paused', 'completed', 'failed', 'cancelled'
        self.progress = 0
        self.created_at = int(time.time())
        self.started_at: Optional[int] = None
        self.completed_at: Optional[int] = None
        self.affected_files: List[str] = []
        self.logs: List[str] = [f"Task queued: '{title}'"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode,
            "priority": self.priority,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "affected_files": self.affected_files,
            "logs": self.logs,
            "elapsed_seconds": (
                (self.completed_at or int(time.time())) - (self.started_at or self.created_at)
            ) if self.started_at else 0
        }


class TaskQueueManager:
    """Manages ordered queue of agent tasks with priority and controls."""

    def __init__(self):
        self.tasks: List[TaskItem] = []

    def enqueue(self, title: str, mode: str = "Agent", priority: str = "medium") -> TaskItem:
        item = TaskItem(title, mode, priority)
        # Higher priority items are placed ahead of lower priority queued items
        if priority == "high":
            insert_idx = 0
            while insert_idx < len(self.tasks) and self.tasks[insert_idx].status in ("running", "paused"):
                insert_idx += 1
            self.tasks.insert(insert_idx, item)
        else:
            self.tasks.append(item)
        return item

    def get_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tasks]

    def update_status(self, task_id: str, status: str, progress: int = None, log_msg: str = None) -> Optional[TaskItem]:
        for t in self.tasks:
            if t.id == task_id:
                t.status = status
                if status == "running" and not t.started_at:
                    t.started_at = int(time.time())
                elif status in ("completed", "failed", "cancelled"):
                    t.completed_at = int(time.time())
                if progress is not None:
                    t.progress = min(100, max(0, progress))
                if log_msg:
                    t.logs.append(log_msg)
                return t
        return None

    def pause_task(self, task_id: str) -> bool:
        return self.update_status(task_id, "paused", log_msg="Task paused by user") is not None

    def resume_task(self, task_id: str) -> bool:
        return self.update_status(task_id, "queued", log_msg="Task resumed") is not None

    def cancel_task(self, task_id: str) -> bool:
        return self.update_status(task_id, "cancelled", log_msg="Task cancelled") is not None

    def clear_completed(self):
        self.tasks = [t for t in self.tasks if t.status not in ("completed", "cancelled", "failed")]


global_task_queue = TaskQueueManager()
