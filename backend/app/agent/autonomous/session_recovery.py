"""
Session State Recovery & Persistence — Step 28 requirement.

Persists task contract, execution plan, checkpoint history, and repair status to disk,
allowing seamless session resumption if the IDE or backend process restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("devpilot.autonomous.session_recovery")


@dataclass
class SessionStateSnapshot:
    session_id: str
    task_goal: str
    contract_data: Dict[str, Any]
    plan_data: Dict[str, Any]
    current_step_id: Optional[str]
    repair_rounds: int
    changed_files: List[str]
    verification_status: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_goal": self.task_goal,
            "contract_data": self.contract_data,
            "plan_data": self.plan_data,
            "current_step_id": self.current_step_id,
            "repair_rounds": self.repair_rounds,
            "changed_files": self.changed_files,
            "verification_status": self.verification_status,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionStateSnapshot":
        return cls(
            session_id=data.get("session_id", ""),
            task_goal=data.get("task_goal", ""),
            contract_data=data.get("contract_data", {}),
            plan_data=data.get("plan_data", {}),
            current_step_id=data.get("current_step_id"),
            repair_rounds=data.get("repair_rounds", 0),
            changed_files=data.get("changed_files", []),
            verification_status=data.get("verification_status", "unverified"),
            status=data.get("status", "IDLE"),
        )


class SessionRecoveryManager:
    """Manages session snapshot persistence and recovery."""

    def __init__(self, storage_dir: str) -> None:
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def save_snapshot(self, snapshot: SessionStateSnapshot) -> str:
        filepath = os.path.join(self.storage_dir, f"session_{snapshot.session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        return filepath

    def load_snapshot(self, session_id: str) -> Optional[SessionStateSnapshot]:
        filepath = os.path.join(self.storage_dir, f"session_{session_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionStateSnapshot.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load session snapshot for {session_id}: {e}")
            return None
