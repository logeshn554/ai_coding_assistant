import os
import json
import tempfile
from typing import Any, Dict, List
from agent_os.learning.interfaces import IMemoryManager

class MemoryKernelManager(IMemoryManager):
    """Concrete Memory Kernel managing structured agent execution states independently of chat transcripts."""
    def __init__(self) -> None:
        self.clear_all()

    def set_current_task(self, task: str) -> None:
        self._current_task = task

    def get_current_task(self) -> str | None:
        return self._current_task

    def set_current_plan(self, plan: Dict[str, Any]) -> None:
        self._current_plan = plan

    def get_current_plan(self) -> Dict[str, Any] | None:
        return self._current_plan

    def set_repository_state(self, state: Dict[str, Any]) -> None:
        self._repository_state = state

    def get_repository_state(self) -> Dict[str, Any] | None:
        return self._repository_state

    def add_artifact(self, name: str, artifact: Dict[str, Any]) -> None:
        self._artifacts[name] = artifact

    def get_artifacts(self) -> Dict[str, Any]:
        return self._artifacts

    def add_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        self._events.append({
            "type": event_type,
            "payload": payload
        })

    def get_events(self) -> List[Dict[str, Any]]:
        return self._events

    def set_current_patch(self, patch: Dict[str, Any]) -> None:
        self._current_patch = patch

    def get_current_patch(self) -> Dict[str, Any] | None:
        return self._current_patch

    def set_diagnostics(self, diagnostics: List[Dict[str, Any]]) -> None:
        self._diagnostics = diagnostics

    def get_diagnostics(self) -> List[Dict[str, Any]]:
        return self._diagnostics

    def clear_all(self) -> None:
        self._current_task = None
        self._current_plan = None
        self._repository_state = None
        self._artifacts = {}
        self._events = []
        self._current_patch = None
        self._diagnostics = []

    def persist_to_disk(self, filepath: str) -> None:
        state_dict = {
            "current_task": self._current_task,
            "current_plan": self._current_plan,
            "repository_state": self._repository_state,
            "artifacts": self._artifacts,
            "events": self._events,
            "current_patch": self._current_patch,
            "diagnostics": self._diagnostics
        }

        # Atomic replacement: write to a temporary file in the same directory, flush/fsync, and rename
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as temp_file:
            json.dump(state_dict, temp_file, indent=2, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = temp_file.name

        try:
            # Atomic replace (overwrites target file)
            os.replace(temp_path, filepath)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def load_from_disk(self, filepath: str) -> None:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Memory state file '{filepath}' does not exist.")
            
        with open(filepath, "r", encoding="utf-8") as f:
            state_dict = json.load(f)

        self._current_task = state_dict.get("current_task")
        self._current_plan = state_dict.get("current_plan")
        self._repository_state = state_dict.get("repository_state")
        self._artifacts = state_dict.get("artifacts", {})
        self._events = state_dict.get("events", [])
        self._current_patch = state_dict.get("current_patch")
        self._diagnostics = state_dict.get("diagnostics", [])
