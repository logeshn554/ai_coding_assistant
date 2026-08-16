"""
memory_manager.py — Persistent AI Project Memory Engine for Antigravity.

Manages permanent project memory stored inside `.devpilot/memory.json`
in the workspace root directory. Retains project architecture, folder structure,
coding conventions, theme system, state management rules, long-term goals,
previous AI edits, user preferences, and known issues.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("devpilot.memory")

_memory_lock = threading.Lock()


class MemoryManager:
    """
    Manages loading, updating, searching, and persisting project memory
    to `.devpilot/memory.json`.
    """

    DEFAULT_MEMORY: dict[str, Any] = {
        "version": "1.0.0",
        "project_name": "DevPilot Workspace",
        "architecture": {
            "pattern": "Component-Based Modular Architecture",
            "state_management": "React Context / Zustand",
            "styling": "TailwindCSS / Vanilla CSS",
            "api_style": "REST / WebSockets",
        },
        "conventions": [
            {
                "id": "conv_1",
                "category": "convention",
                "title": "8px Spacing Grid",
                "content": "Always use 8px multiples for element spacing and padding.",
                "enabled": True,
            },
            {
                "id": "conv_2",
                "category": "architecture",
                "title": "Component Modularity",
                "content": "Keep component files under 300 lines of code.",
                "enabled": True,
            },
        ],
        "long_term_goals": [],
        "frequently_modified_files": [],
        "previous_ai_edits": [],
        "known_issues": [],
        "user_preferences": {
            "auto_apply_diffs": False,
            "theme": "dark",
            "max_token_budget": 128000,
        },
    }

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = workspace_root
        self._memory_data: dict[str, Any] = self.DEFAULT_MEMORY.copy()
        if workspace_root:
            self.load_memory()

    def _get_memory_path(self) -> Path | None:
        if not self.workspace_root or not os.path.isdir(self.workspace_root):
            return None
        devpilot_dir = Path(self.workspace_root) / ".devpilot"
        devpilot_dir.mkdir(exist_ok=True)
        return devpilot_dir / "memory.json"

    def load_memory(self) -> dict[str, Any]:
        """Loads memory from .devpilot/memory.json if present."""
        path = self._get_memory_path()
        if not path or not path.exists():
            return self._memory_data

        with _memory_lock:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                data = json.loads(content)
                if isinstance(data, dict):
                    self._memory_data = {**self.DEFAULT_MEMORY, **data}
            except Exception as e:
                logger.error(f"Failed to read .devpilot/memory.json: {e}")

        return self._memory_data

    def save_memory(self) -> bool:
        """Persists memory data to disk with thread safety."""
        path = self._get_memory_path()
        if not path:
            return False

        with _memory_lock:
            try:
                path.write_text(
                    json.dumps(self._memory_data, indent=2), encoding="utf-8"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to write .devpilot/memory.json: {e}")
                return False

    def get_memory(self) -> dict[str, Any]:
        return self._memory_data

    def add_convention(
        self, title: str, content: str, category: str = "convention"
    ) -> dict[str, Any]:
        convs = self._memory_data.setdefault("conventions", [])
        new_item = {
            "id": f"m_{abs(hash(title + content))}",
            "category": category,
            "title": title,
            "content": content,
            "enabled": True,
        }
        convs.insert(0, new_item)
        self.save_memory()
        return new_item

    def toggle_convention(self, item_id: str) -> bool:
        convs = self._memory_data.get("conventions", [])
        for c in convs:
            if c.get("id") == item_id:
                c["enabled"] = not c.get("enabled", True)
                self.save_memory()
                return True
        return False

    def delete_convention(self, item_id: str) -> bool:
        convs = self._memory_data.get("conventions", [])
        initial_len = len(convs)
        self._memory_data["conventions"] = [
            c for c in convs if c.get("id") != item_id
        ]
        if len(self._memory_data["conventions"]) < initial_len:
            self.save_memory()
            return True
        return False

    def record_ai_edit(self, file_path: str, summary: str):
        edits = self._memory_data.setdefault("previous_ai_edits", [])
        import time

        edits.insert(
            0,
            {
                "path": file_path,
                "summary": summary,
                "timestamp": int(time.time()),
            },
        )
        self._memory_data["previous_ai_edits"] = edits[:50]  # retain last 50 edits

        # Update frequently modified files
        freq = self._memory_data.setdefault("frequently_modified_files", [])
        if file_path in freq:
            freq.remove(file_path)
        freq.insert(0, file_path)
        self._memory_data["frequently_modified_files"] = freq[:20]

        self.save_memory()

    def search_memory(self, query: str) -> list[dict[str, Any]]:
        """Performs search across memory conventions, goals, and edits."""
        q = query.lower().strip()
        if not q:
            return self._memory_data.get("conventions", [])

        results = []
        for c in self._memory_data.get("conventions", []):
            if q in c.get("title", "").lower() or q in c.get("content", "").lower():
                results.append(c)

        for edit in self._memory_data.get("previous_ai_edits", []):
            if q in edit.get("path", "").lower() or q in edit.get("summary", "").lower():
                results.append(
                    {
                        "id": f"edit_{edit.get('timestamp')}",
                        "category": "ai_edit",
                        "title": f"Edit: {edit.get('path')}",
                        "content": edit.get("summary"),
                        "enabled": True,
                    }
                )

        return results


# Global memory manager instance
global_memory_manager = MemoryManager()
