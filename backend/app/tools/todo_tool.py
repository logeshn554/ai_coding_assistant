"""Todo tool – agent-managed structured task checklist.

Exposes two async agent-facing functions:
  - ``todo_write(session, args)`` — create or update the session todo list
  - ``todo_read(session, args)``  — read the current todo list

The todo list is persisted in ``session.memory["__agent_todos__"]`` as a
list of dicts with keys ``id``, ``text``, ``status``.
"""
from __future__ import annotations

import json
from typing import Any

_TODO_KEY = "__agent_todos__"
_VALID_STATUSES = {"pending", "in_progress", "done"}


def _render_todos(todos: list[dict]) -> str:
    """Format todos as a readable checklist string."""
    if not todos:
        return "Todo list is empty."
    lines = ["## Agent Todo List\n"]
    status_icons = {"pending": "☐", "in_progress": "▶", "done": "☑"}
    for item in todos:
        icon = status_icons.get(item.get("status", "pending"), "☐")
        lines.append(f"{icon} [{item['id']}] {item['text']}  ({item.get('status', 'pending')})")
    return "\n".join(lines)


async def todo_write(session: Any, args: dict[str, Any]) -> str:
    """Create or update the agent todo list.

    Args:
        session: Active AgentSession (provides memory store).
        args:
            todos (list, required): Full list of todo items. Each item must
                have ``text`` (str). Optional fields: ``id`` (str, auto-assigned
                if missing), ``status`` (``pending``|``in_progress``|``done``,
                defaults to ``pending``).
            merge (bool, optional): If True, merge with existing list (update
                matching ids, append new ones). If False (default), replace
                the list entirely.

    Returns:
        Confirmation message with the rendered todo list.
    """
    raw_todos = args.get("todos")
    if raw_todos is None:
        return "Error: 'todos' argument is required for todo_write."

    if isinstance(raw_todos, str):
        try:
            raw_todos = json.loads(raw_todos)
        except json.JSONDecodeError:
            return "Error: 'todos' must be a JSON array of objects."

    if not isinstance(raw_todos, list):
        return "Error: 'todos' must be a list/array."

    merge: bool = bool(args.get("merge", False))
    memory = getattr(session, "memory", {})
    existing: list[dict] = memory.get(_TODO_KEY, []) if merge else []
    existing_by_id = {item["id"]: item for item in existing}

    # Auto-generate sequential ids
    next_id = max((int(item["id"]) for item in existing if str(item.get("id", "")).isdigit()), default=0) + 1

    for item in raw_todos:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        item_id = str(item.get("id") or next_id)
        if not item_id.isdigit():
            item_id = str(next_id)
        next_id = max(next_id, int(item_id) if item_id.isdigit() else next_id) + 1
        status = item.get("status", "pending")
        if status not in _VALID_STATUSES:
            status = "pending"
        existing_by_id[item_id] = {"id": item_id, "text": text, "status": status}

    final_todos = list(existing_by_id.values())
    memory[_TODO_KEY] = final_todos

    return f"Todo list updated ({len(final_todos)} items).\n\n" + _render_todos(final_todos)


async def todo_read(session: Any, args: dict[str, Any]) -> str:
    """Read the current agent todo list.

    Args:
        session: Active AgentSession (provides memory store).
        args: (unused, accepted for API consistency)

    Returns:
        Rendered todo checklist, or a message if the list is empty.
    """
    memory = getattr(session, "memory", {})
    todos: list[dict] = memory.get(_TODO_KEY, [])
    return _render_todos(todos)
