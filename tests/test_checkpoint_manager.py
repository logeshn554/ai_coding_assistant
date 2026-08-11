"""
Tests for checkpoint manager (Phase 6a).
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from agent_os.agent.checkpoint_manager import CheckpointManager, ExecutionReplayer


class TestCheckpointManager:
    """Test checkpoint functionality."""

    @pytest.fixture
    def checkpoint_dir(self):
        """Create temporary checkpoint directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, checkpoint_dir):
        """Create checkpoint manager."""
        return CheckpointManager(checkpoint_dir)

    def test_save_checkpoint(self, manager):
        """Test saving a checkpoint."""
        checkpoint = manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[{"type": "test", "data": "test"}],
            conversation_history=[],
            files_modified=["file1.py"],
        )

        assert checkpoint is not None
        assert checkpoint.run_id == "run-1"
        assert checkpoint.state == "running"
        assert checkpoint.files_modified == ["file1.py"]

    def test_load_checkpoint(self, manager):
        """Test loading a checkpoint."""
        # Save
        saved = manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[{"type": "test"}],
            conversation_history=[{"role": "user", "content": "test"}],
            files_modified=["file1.py"],
        )

        # Load
        loaded = manager.load_checkpoint(saved.checkpoint_id)

        assert loaded["metadata"]["run_id"] == "run-1"
        assert loaded["metadata"]["state"] == "running"
        assert len(loaded["execution_log"]) == 1
        assert len(loaded["conversation_history"]) == 1

    def test_get_latest_checkpoint(self, manager):
        """Test getting latest checkpoint."""
        # Save multiple checkpoints
        manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[],
            conversation_history=[],
        )

        import time
        time.sleep(0.1)

        manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="completed",
            agent_context=None,
            execution_log=[],
            conversation_history=[],
        )

        latest = manager.get_latest_checkpoint("run-1")
        assert latest is not None
        assert latest["state"] == "completed"

    def test_list_checkpoints(self, manager):
        """Test listing checkpoints."""
        # Save 3 checkpoints
        for i in range(3):
            manager.save_checkpoint(
                run_id="run-1",
                task_id="task-1",
                agent_id="agent-1",
                attempt_id="attempt-1",
                state=f"state-{i}",
                agent_context=None,
                execution_log=[],
                conversation_history=[],
            )

            import time
            time.sleep(0.01)

        checkpoints = manager.list_checkpoints("run-1")
        assert len(checkpoints) == 3

    def test_delete_checkpoint(self, manager):
        """Test deleting a checkpoint."""
        saved = manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[],
            conversation_history=[],
        )

        # Delete
        deleted = manager.delete_checkpoint(saved.checkpoint_id)
        assert deleted

        # Try to load (should fail)
        with pytest.raises(FileNotFoundError):
            manager.load_checkpoint(saved.checkpoint_id)

    def test_cleanup_old_checkpoints(self, manager):
        """Test cleaning up old checkpoints."""
        # Save 7 checkpoints
        for i in range(7):
            manager.save_checkpoint(
                run_id="run-1",
                task_id="task-1",
                agent_id="agent-1",
                attempt_id="attempt-1",
                state=f"state-{i}",
                agent_context=None,
                execution_log=[],
                conversation_history=[],
            )

            import time
            time.sleep(0.01)

        # Cleanup, keeping only 3
        deleted = manager.cleanup_old_checkpoints("run-1", keep_last_n=3)
        assert deleted == 4

        # Verify only 3 remain
        remaining = manager.list_checkpoints("run-1")
        assert len(remaining) == 3

    def test_create_snapshot(self, manager):
        """Test creating a snapshot."""
        # Create a checkpoint first
        manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[],
            conversation_history=[],
        )

        # Create snapshot
        snapshot_id = manager.create_snapshot(
            run_id="run-1",
            tag="stable",
            description="Stable version"
        )

        assert snapshot_id is not None
        assert "snapshot" in snapshot_id
        assert "stable" in snapshot_id

    def test_get_checkpoint_diff(self, manager):
        """Test getting differences between checkpoints."""
        # Save two checkpoints
        cp1 = manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="state-1",
            agent_context=None,
            execution_log=[{"event": 1}],
            conversation_history=[],
            files_modified=["file1.py"],
        )

        import time
        time.sleep(0.01)

        cp2 = manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="state-2",
            agent_context=None,
            execution_log=[{"event": 1}, {"event": 2}],
            conversation_history=[],
            files_modified=["file1.py", "file2.py"],
        )

        diff = manager.get_checkpoint_diff(cp1.checkpoint_id, cp2.checkpoint_id)

        assert diff["state_changed"]
        assert "file2.py" in diff["files_modified_diff"]["added"]
        assert diff["events_added"] == 1


class TestExecutionReplayer:
    """Test execution replay functionality."""

    @pytest.fixture
    def replayer(self):
        """Create execution replayer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(tmpdir)
            yield ExecutionReplayer(manager)

    def test_can_resume(self, replayer):
        """Test checking if run can be resumed."""
        # No checkpoints yet
        assert not replayer.can_resume("run-1")

        # Create checkpoint
        replayer.checkpoint_manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[],
            conversation_history=[],
        )

        # Now can resume
        assert replayer.can_resume("run-1")

    def test_get_resume_point(self, replayer):
        """Test getting resume point."""
        # Create checkpoint
        replayer.checkpoint_manager.save_checkpoint(
            run_id="run-1",
            task_id="task-1",
            agent_id="agent-1",
            attempt_id="attempt-1",
            state="running",
            agent_context=None,
            execution_log=[{"event": 1}],
            conversation_history=[{"role": "user", "content": "hello"}],
            files_modified=["file1.py"],
        )

        resume_point = replayer.get_resume_point("run-1")

        assert resume_point["state"] == "running"
        assert resume_point["files_modified"] == ["file1.py"]
        assert len(resume_point["conversation_history"]) == 1
        assert len(resume_point["execution_log"]) == 1

    def test_get_audit_trail(self, replayer):
        """Test getting audit trail."""
        # Create multiple checkpoints
        for i in range(3):
            replayer.checkpoint_manager.save_checkpoint(
                run_id="run-1",
                task_id="task-1",
                agent_id="agent-1",
                attempt_id="attempt-1",
                state=f"state-{i}",
                agent_context=None,
                execution_log=[],
                conversation_history=[],
                files_modified=[f"file{i}.py"],
            )

            import time
            time.sleep(0.01)

        trail = replayer.get_audit_trail("run-1")

        assert len(trail) == 3
        # Trail should be in chronological order
        assert trail[0]["state"] == "state-2"
        assert trail[2]["state"] == "state-0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
