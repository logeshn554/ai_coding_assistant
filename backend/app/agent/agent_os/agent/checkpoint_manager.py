"""
Checkpoint manager for durable state persistence and execution resumption.

Features:
  - Save execution state at each step
  - Restore from checkpoints on restart
  - Maintain audit trail
  - Support rollback to previous states
  - Efficient incremental snapshots
"""

import json
import os
import hashlib
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from .interfaces import Task, AgentContext, AgentResult
from .event_system import Event


@dataclass
class ExecutionCheckpoint:
    """Single checkpoint in execution history."""
    checkpoint_id: str
    run_id: str
    task_id: Optional[str]
    agent_id: Optional[str]
    attempt_id: Optional[str]
    timestamp: datetime
    state: str  # Agent state
    files_modified: List[str]
    events_count: int
    conversation_history_len: int
    metadata: Dict[str, Any]


class CheckpointManager:
    """Manages persistent checkpoints for agent execution."""

    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        run_id: str,
        task_id: Optional[str],
        agent_id: Optional[str],
        attempt_id: Optional[str],
        state: str,
        agent_context: Optional[AgentContext],
        execution_log: List[Dict[str, Any]],
        conversation_history: List[Any],
        files_modified: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionCheckpoint:
        """
        Save execution checkpoint.

        Args:
            run_id: Run identifier
            task_id: Task identifier
            agent_id: Agent identifier
            attempt_id: Attempt identifier
            state: Current agent state
            agent_context: Agent context
            execution_log: Execution log entries
            conversation_history: LLM conversation history
            files_modified: Files modified so far
            metadata: Additional metadata

        Returns:
            ExecutionCheckpoint object
        """
        checkpoint_id = self._generate_checkpoint_id(run_id, task_id, agent_id)

        # Create checkpoint object
        checkpoint = ExecutionCheckpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            task_id=task_id,
            agent_id=agent_id,
            attempt_id=attempt_id,
            timestamp=datetime.utcnow(),
            state=state,
            files_modified=files_modified or [],
            events_count=len(execution_log),
            conversation_history_len=len(conversation_history),
            metadata=metadata or {},
        )

        # Save checkpoint metadata
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        metadata_file = checkpoint_path / "checkpoint.json"
        metadata_file.write_text(json.dumps(
            {
                **asdict(checkpoint),
                "timestamp": checkpoint.timestamp.isoformat(),
            },
            indent=2
        ))

        # Save execution log
        log_file = checkpoint_path / "execution_log.json"
        log_file.write_text(json.dumps(execution_log, indent=2, default=str))

        # Save conversation history as JSON
        history_file = checkpoint_path / "conversation_history.json"
        history_file.write_text(json.dumps(conversation_history, indent=2, default=str))

        # Save agent context
        if agent_context:
            context_file = checkpoint_path / "agent_context.json"
            context_file.write_text(json.dumps(
                {
                    "run_id": agent_context.run_id,
                    "task_id": agent_context.task.task_id,
                    "agent_type": agent_context.task.agent_type,
                    "workspace_root": agent_context.workspace_root,
                    "model_provider": agent_context.model_provider,
                    "model_name": agent_context.model_name,
                },
                indent=2
            ))

        return checkpoint

    def load_checkpoint(
        self,
        checkpoint_id: str,
    ) -> Dict[str, Any]:
        """
        Load checkpoint data.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Dict with checkpoint data including:
              - metadata: CheckpointMetadata
              - execution_log: List[Dict]
              - conversation_history: List[Any]
              - agent_context: Dict
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")

        # Load metadata
        metadata_file = checkpoint_path / "checkpoint.json"
        metadata = json.loads(metadata_file.read_text())

        # Load execution log
        log_file = checkpoint_path / "execution_log.json"
        execution_log = json.loads(log_file.read_text()) if log_file.exists() else []

        # Load conversation history
        json_history_file = checkpoint_path / "conversation_history.json"
        if json_history_file.exists():
            conversation_history = json.loads(json_history_file.read_text())
        else:
            conversation_history = []

        # Load agent context
        context_file = checkpoint_path / "agent_context.json"
        agent_context = json.loads(context_file.read_text()) if context_file.exists() else None

        return {
            "metadata": metadata,
            "execution_log": execution_log,
            "conversation_history": conversation_history,
            "agent_context": agent_context,
        }

    def get_latest_checkpoint(self, run_id: str) -> Optional[ExecutionCheckpoint]:
        """Get the latest checkpoint for a run."""
        run_dir = self.checkpoint_dir / run_id
        if not run_dir.exists():
            return None

        checkpoints = []
        for checkpoint_dir in run_dir.iterdir():
            if checkpoint_dir.is_dir():
                metadata_file = checkpoint_dir / "checkpoint.json"
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    checkpoints.append(metadata)

        if not checkpoints:
            return None

        # Return the most recent
        latest = max(checkpoints, key=lambda c: c["timestamp"])
        return latest

    def list_checkpoints(self, run_id: str) -> List[Dict[str, Any]]:
        """List all checkpoints for a run."""
        run_dir = self.checkpoint_dir / run_id
        if not run_dir.exists():
            return []

        checkpoints = []
        for checkpoint_dir in run_dir.iterdir():
            if checkpoint_dir.is_dir():
                metadata_file = checkpoint_dir / "checkpoint.json"
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    checkpoints.append(metadata)

        # Sort by timestamp descending
        checkpoints.sort(key=lambda c: c["timestamp"], reverse=True)
        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        if checkpoint_path.exists():
            import shutil
            shutil.rmtree(checkpoint_path)
            return True
        return False

    def cleanup_old_checkpoints(self, run_id: str, keep_last_n: int = 5) -> int:
        """
        Clean up old checkpoints, keeping only the last N.

        Args:
            run_id: Run identifier
            keep_last_n: Number of checkpoints to keep

        Returns:
            Number of checkpoints deleted
        """
        checkpoints = self.list_checkpoints(run_id)

        deleted = 0
        for checkpoint in checkpoints[keep_last_n:]:
            if self.delete_checkpoint(checkpoint["checkpoint_id"]):
                deleted += 1

        return deleted

    def create_snapshot(
        self,
        run_id: str,
        tag: str,
        description: str,
    ) -> str:
        """
        Create a named snapshot for a run.

        Args:
            run_id: Run identifier
            tag: Snapshot tag/name
            description: Human-readable description

        Returns:
            Snapshot ID
        """
        latest = self.get_latest_checkpoint(run_id)
        if not latest:
            raise ValueError(f"No checkpoints found for run {run_id}")

        snapshot_id = f"{run_id}/snapshot-{tag}-{datetime.utcnow().isoformat().replace(':', '-')}"
        snapshot_path = self.checkpoint_dir / snapshot_id
        snapshot_path.mkdir(parents=True, exist_ok=True)

        # Write snapshot metadata
        snapshot_file = snapshot_path / "snapshot.json"
        snapshot_file.write_text(json.dumps({
            "snapshot_id": snapshot_id,
            "tag": tag,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "based_on_checkpoint": latest["checkpoint_id"],
        }, indent=2))

        return snapshot_id

    def get_checkpoint_diff(
        self,
        checkpoint_id_1: str,
        checkpoint_id_2: str,
    ) -> Dict[str, Any]:
        """
        Get differences between two checkpoints.

        Args:
            checkpoint_id_1: First checkpoint
            checkpoint_id_2: Second checkpoint

        Returns:
            Dict with differences
        """
        cp1 = self.load_checkpoint(checkpoint_id_1)
        cp2 = self.load_checkpoint(checkpoint_id_2)

        return {
            "state_changed": cp1["metadata"]["state"] != cp2["metadata"]["state"],
            "files_modified_diff": {
                "added": set(cp2["metadata"]["files_modified"]) - set(cp1["metadata"]["files_modified"]),
                "removed": set(cp1["metadata"]["files_modified"]) - set(cp2["metadata"]["files_modified"]),
            },
            "events_added": cp2["metadata"]["events_count"] - cp1["metadata"]["events_count"],
            "conversation_turns_added": cp2["metadata"]["conversation_history_len"] - cp1["metadata"]["conversation_history_len"],
        }

    def _generate_checkpoint_id(self, run_id: str, task_id: Optional[str], agent_id: Optional[str]) -> str:
        """Generate unique checkpoint ID."""
        content = f"{run_id}:{task_id}:{agent_id}:{datetime.utcnow().isoformat()}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"{run_id}/checkpoint-{hash_val}"

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get filesystem path for checkpoint."""
        return self.checkpoint_dir / checkpoint_id


class ExecutionReplayer:
    """Replays execution from checkpoints."""

    def __init__(self, checkpoint_manager: CheckpointManager):
        """
        Initialize execution replayer.

        Args:
            checkpoint_manager: CheckpointManager instance
        """
        self.checkpoint_manager = checkpoint_manager

    def can_resume(self, run_id: str) -> bool:
        """Check if run can be resumed from checkpoint."""
        latest = self.checkpoint_manager.get_latest_checkpoint(run_id)
        return latest is not None

    def get_resume_point(self, run_id: str) -> Dict[str, Any]:
        """
        Get resume point for a run.

        Returns:
            Dict with:
              - checkpoint_id: Which checkpoint to resume from
              - state: Agent state at resume point
              - files_modified: Files already modified
              - conversation_history: Prior conversation
        """
        latest = self.checkpoint_manager.get_latest_checkpoint(run_id)
        if not latest:
            raise ValueError(f"No checkpoint found for run {run_id}")

        checkpoint_data = self.checkpoint_manager.load_checkpoint(latest["checkpoint_id"])

        return {
            "checkpoint_id": latest["checkpoint_id"],
            "state": latest["state"],
            "files_modified": latest["files_modified"],
            "conversation_history": checkpoint_data["conversation_history"],
            "execution_log": checkpoint_data["execution_log"],
            "timestamp": latest["timestamp"],
        }

    async def replay_to_state(
        self,
        run_id: str,
        target_state: str,
        agent: Any,
    ) -> bool:
        """
        Replay execution to a specific state.

        Args:
            run_id: Run identifier
            target_state: Target agent state
            agent: Agent instance to replay into

        Returns:
            True if successfully replayed to target
        """
        checkpoints = self.checkpoint_manager.list_checkpoints(run_id)

        # Find checkpoint at or before target state
        target_checkpoint = None
        for checkpoint in reversed(checkpoints):
            if checkpoint["state"] == target_state or checkpoint["timestamp"] < datetime.utcnow().isoformat():
                target_checkpoint = checkpoint
                break

        if not target_checkpoint:
            return False

        # Load checkpoint data
        checkpoint_data = self.checkpoint_manager.load_checkpoint(target_checkpoint["checkpoint_id"])

        # Restore agent state
        agent._conversation_history = checkpoint_data["conversation_history"]
        agent._execution_log = checkpoint_data["execution_log"]

        return True

    def get_audit_trail(self, run_id: str) -> List[Dict[str, Any]]:
        """Get complete audit trail for a run (newest first)."""
        checkpoints = self.checkpoint_manager.list_checkpoints(run_id)

        trail = []
        for checkpoint in checkpoints:
            trail.append({
                "checkpoint_id": checkpoint["checkpoint_id"],
                "timestamp": checkpoint["timestamp"],
                "state": checkpoint["state"],
                "files_modified": checkpoint["files_modified"],
                "events": checkpoint["events_count"],
            })

        return trail
