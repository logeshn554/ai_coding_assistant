import difflib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileSnapshot:
    filepath: str
    original_content: str | None
    exists_before: bool
    modified_at: float = field(default_factory=time.time)

@dataclass
class ChangeSet:
    task_id: str
    created_at: float = field(default_factory=time.time)
    snapshots: dict[str, FileSnapshot] = field(default_factory=dict)
    applied_edits: dict[str, str] = field(default_factory=dict)  # filepath -> new_content
    is_committed: bool = False
    is_rolled_back: bool = False

class TransactionalFileSystem:
    """Provides atomic change sets, snapshotting, diff previews, and instant rollbacks for AI file modifications."""

    def __init__(self):
        self._active_change_sets: dict[str, ChangeSet] = {}

    def get_or_create_change_set(self, task_id: str) -> ChangeSet:
        if task_id not in self._active_change_sets:
            self._active_change_sets[task_id] = ChangeSet(task_id=task_id)
        return self._active_change_sets[task_id]

    def stage_write(self, task_id: str, filepath: str, new_content: str) -> dict[str, Any]:
        """Stages a file edit under snapshot protection before writing to disk."""
        abs_path = str(Path(filepath).resolve())
        change_set = self.get_or_create_change_set(task_id)

        # Snapshot file state prior to first edit in this change set
        if abs_path not in change_set.snapshots:
            exists = os.path.exists(abs_path)
            orig_content = None
            if exists:
                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                        orig_content = f.read()
                except Exception:
                    orig_content = ""
            change_set.snapshots[abs_path] = FileSnapshot(
                filepath=abs_path,
                original_content=orig_content,
                exists_before=exists
            )

        # Perform atomic write to disk
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        temp_path = f"{abs_path}.loopix_tmp_{int(time.time()*1000)}"
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Replace target file atomically
        shutil.move(temp_path, abs_path)
        change_set.applied_edits[abs_path] = new_content

        return {
            "task_id": task_id,
            "filepath": abs_path,
            "status": "staged_and_applied",
            "snapshot_recorded": True
        }

    def rollback_task(self, task_id: str) -> dict[str, Any]:
        """Rolls back all file modifications made by a specific agent task."""
        if task_id not in self._active_change_sets:
            return {"success": False, "reason": f"No change set found for task_id {task_id}"}
        
        change_set = self._active_change_sets[task_id]
        if change_set.is_rolled_back:
            return {"success": True, "message": "Change set was already rolled back."}

        restored_files = []
        deleted_files = []
        errors = []

        for abs_path, snapshot in change_set.snapshots.items():
            try:
                if snapshot.exists_before:
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(snapshot.original_content or "")
                    restored_files.append(abs_path)
                else:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        deleted_files.append(abs_path)
            except Exception as e:
                errors.append({"filepath": abs_path, "error": str(e)})

        change_set.is_rolled_back = True
        return {
            "success": len(errors) == 0,
            "task_id": task_id,
            "restored_files": restored_files,
            "deleted_created_files": deleted_files,
            "errors": errors
        }

    def get_task_diff(self, task_id: str) -> list[dict[str, Any]]:
        """Generates unified diffs for all files in a change set."""
        if task_id not in self._active_change_sets:
            return []

        change_set = self._active_change_sets[task_id]
        diffs = []

        for abs_path, snapshot in change_set.snapshots.items():
            orig = (snapshot.original_content or "").splitlines(keepends=True)
            curr_content = change_set.applied_edits.get(abs_path, "")
            curr = curr_content.splitlines(keepends=True)

            diff_lines = list(difflib.unified_diff(
                orig, curr,
                fromfile=f"a/{os.path.basename(abs_path)}",
                tofile=f"b/{os.path.basename(abs_path)}"
            ))
            diff_text = "".join(diff_lines)

            diffs.append({
                "filepath": abs_path,
                "diff": diff_text,
                "created": not snapshot.exists_before
            })

        return diffs

transactional_fs = TransactionalFileSystem()
