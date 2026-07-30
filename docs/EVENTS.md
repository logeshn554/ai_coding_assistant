# AgentOS Event Schema

This document details the events emitted across the central `IEventBus` system.

## 1. Task State Changed Event
*   **Topic**: `task_state_changed`
*   **Emitted by**: `TaskStateMachine`
*   **Reason**: Whenever the task transitions to a new state or rolls back.
*   **Payload Schema**:
    ```json
    {
      "old_state": "PLAN",
      "new_state": "EDIT"
    }
    ```

## 2. File Scanned Event
*   **Topic**: `file_scanned`
*   **Emitted by**: `RepositoryKernel`
*   **Reason**: Dispatched after a file is successfully parsed and loaded into SQLite.
*   **Payload Schema**:
    ```json
    {
      "file_path": "src/main.py",
      "symbols_count": 3
    }
    ```

## 3. Transaction Committed Event
*   **Topic**: `transaction_committed`
*   **Emitted by**: `FileTransaction` (during commit)
*   **Reason**: Emitted when changes are written to the disk.
*   **Payload Schema**:
    ```json
    {
      "modified_files": ["db.py", "main.py"]
    }
    ```
