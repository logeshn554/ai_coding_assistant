"""
File Transaction — Implements multi-file transaction blocks supporting commit and automatic rollback.
"""
from __future__ import annotations

import logging
import os
from enum import Enum

logger = logging.getLogger("loopix.merge.file_transaction")


class TransactionState(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class TaskTransaction:
    """High-level transaction scope wrapping file operations and agent state."""

    def __init__(self, transaction_id: str, task_description: str):
        self.transaction_id = transaction_id
        self.task_description = task_description
        self.state = TransactionState.CREATED
        self.file_txn = FileTransaction()

    def begin(self) -> None:
        self.state = TransactionState.PLANNED
        self.file_txn.begin()

    def execute(self) -> None:
        self.state = TransactionState.EXECUTING

    def verify(self) -> None:
        self.state = TransactionState.VERIFYING

    def commit(self) -> None:
        self.file_txn.commit()
        self.state = TransactionState.COMMITTED

    def rollback(self) -> None:
        self.file_txn.rollback()
        self.state = TransactionState.ROLLED_BACK


class FileTransaction:
    """Enforces atomic workspace writes by backing up files before modifications."""

    def __init__(self) -> None:
        # Key: file_path -> original content backup
        self._backups: dict[str, str] = {}
        self._active = False

    def begin(self) -> None:
        """Begin a new atomic file transaction."""
        self._backups.clear()
        self._active = True
        logger.debug("File transaction started.")

    def write_file(self, file_path: str, new_content: str) -> None:
        """Write content while backing up original file state."""
        if not self._active:
            raise RuntimeError("No active file transaction. Call begin() first.")

        # Backup if not already backed up during this transaction
        if file_path not in self._backups:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._backups[file_path] = f.read()
            else:
                self._backups[file_path] = ""  # marker for new file creation

        # Perform write
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.debug(f"Transactional write executed on: {file_path}")

    def commit(self) -> None:
        """Commit transaction, finalizing changes."""
        self._backups.clear()
        self._active = False
        logger.info("File transaction committed successfully.")

    def rollback(self) -> None:
        """Rollback all transaction writes, restoring original file states."""
        if not self._active:
            return

        for path, backup_content in self._backups.items():
            try:
                if backup_content == "":
                    # New file created during txn, delete it
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Rollback: Removed newly created file: {path}")
                else:
                    # Restore original content
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(backup_content)
                    logger.info(f"Rollback: Restored backup for: {path}")
            except Exception as e:
                logger.error(f"Failed to restore backup for '{path}' during rollback: {e}")

        self._backups.clear()
        self._active = False
        logger.warning("File transaction rolled back complete.")


# ── Singleton ───────────────────────────────────────────────────────────────

file_transaction = FileTransaction()
