
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..task_queue import global_task_queue

router = APIRouter()


class CreateTaskRequest(BaseModel):
    title: str
    mode: str | None = "Agent"
    priority: str | None = "medium"


class TaskActionRequest(BaseModel):
    task_id: str


@router.get("/api/tasks")
def get_tasks():
    """Returns list of all active and historical agent tasks."""
    return {"tasks": global_task_queue.get_tasks()}


@router.post("/api/tasks")
def enqueue_task(req: CreateTaskRequest):
    """Enqueues a new autonomous agent task."""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")
    item = global_task_queue.enqueue(title=req.title, mode=req.mode or "Agent", priority=req.priority or "medium")
    return {"success": True, "task": item.to_dict()}


@router.post("/api/tasks/{task_id}/pause")
def pause_task(task_id: str):
    """Pauses a queued or running task."""
    ok = global_task_queue.pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task_id": task_id}


@router.post("/api/tasks/{task_id}/resume")
def resume_task(task_id: str):
    """Resumes a paused task."""
    ok = global_task_queue.resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task_id": task_id}


@router.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    """Cancels a task."""
    ok = global_task_queue.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task_id": task_id}


@router.delete("/api/tasks/completed")
def clear_completed_tasks():
    """Clears completed or failed tasks from queue."""
    global_task_queue.clear_completed()
    return {"success": True}
