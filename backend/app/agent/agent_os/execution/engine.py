import ast
import os
import tempfile
from typing import Any

from agent_os.execution.interfaces import ITransaction, ITransactionalExecutionEngine


class MergeConflictError(Exception):
    pass

class PatchSyntaxError(Exception):
    pass

class TransactionError(Exception):
    pass


class FileTransaction(ITransaction):
    """File modification transaction mapping target files to in-memory buffers before committing."""
    def __init__(self, engine: "TransactionalExecutionEngine", agent_name: str = "default_agent") -> None:
        self._engine = engine
        self._agent_name = agent_name
        self._backups: dict[str, str] = {}
        self._updates: dict[str, str] = {}
        self._acquired_locks: list[str] = []
        self._active = False

    def begin(self) -> None:
        self._backups.clear()
        self._updates.clear()
        self._acquired_locks.clear()
        self._active = True

    def apply_patch(self, file_path: str, target_content: str, replacement_content: str) -> None:
        if not self._active:
            raise TransactionError("Transaction is not active. Call begin() first.")

        workspace_root = ""
        if self._engine.registry:
            try:
                from agent_os.core.config import DictionaryConfig
                config = self._engine.registry.resolve(DictionaryConfig)
                workspace_root = config.get("workspace_root")
            except Exception:
                pass

        if workspace_root and not os.path.isabs(file_path):
            abs_path = os.path.abspath(os.path.join(workspace_root, file_path))
        else:
            abs_path = os.path.abspath(file_path)

        normalized_path = os.path.normpath(abs_path).replace("\\", "/")

        # 1. Enforce Pessimistic File Locking
        lock_manager = None
        if self._engine.registry:
            try:
                from agent_os.execution.lock_manager import FileLockManager
                lock_manager = self._engine.registry.resolve(FileLockManager)
            except Exception:
                pass

        if lock_manager:
            acquired = lock_manager.acquire_lock(normalized_path, self._agent_name, exclusive=True)
            if not acquired:
                raise TransactionError(f"TransactionError: File '{os.path.basename(abs_path)}' is locked by another agent.")
            
            if normalized_path not in self._acquired_locks:
                lock_manager.snapshot_file(abs_path)
                self._acquired_locks.append(normalized_path)

        # 2. Determine current content state
        if abs_path in self._updates:
            current_content = self._updates[abs_path]
        else:
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"Target file '{abs_path}' does not exist.")
            with open(abs_path, "r", encoding="utf-8") as f:
                current_content = f.read()
            self._backups[abs_path] = current_content

        # 3. Validate and compile patch
        patched_code = self._engine.validate_patch(
            abs_path, current_content, target_content, replacement_content
        )
        self._updates[abs_path] = patched_code

    def _release_all_locks(self, lock_manager) -> None:
        for path in self._acquired_locks:
            lock_manager.release_lock(path, self._agent_name)
        self._acquired_locks.clear()

    def commit(self) -> None:
        if not self._active:
            raise TransactionError("Transaction is not active.")

        lock_manager = None
        if self._engine.registry:
            try:
                from agent_os.execution.lock_manager import FileLockManager
                lock_manager = self._engine.registry.resolve(FileLockManager)
            except Exception:
                pass

        # 1. Enforce Optimistic lock check (before writing)
        if lock_manager:
            for path in self._acquired_locks:
                if not lock_manager.verify_optimistic_lock(path):
                    self._release_all_locks(lock_manager)
                    self.rollback()
                    raise TransactionError(f"Optimistic lock verification failed: file '{os.path.basename(path)}' was modified externally.")

        committed_files: list[str] = []
        try:
            for filepath, content in self._updates.items():
                # Atomic write to temp file then replace
                dir_name = os.path.dirname(filepath)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                
                with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as temp_file:
                    temp_file.write(content)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                    temp_path = temp_file.name

                try:
                    os.replace(temp_path, filepath)
                    committed_files.append(filepath)
                except Exception:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise
        except Exception as e:
            # Multi-file rollback on commit failures
            for filepath in committed_files:
                original = self._backups.get(filepath)
                if original is not None:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(original)
            self.rollback()
            raise TransactionError(f"Commit failed. Rolled back committed changes. Error: {e!s}")
        finally:
            if lock_manager:
                self._release_all_locks(lock_manager)

        self._active = False

    def rollback(self) -> None:
        lock_manager = None
        if self._engine.registry:
            try:
                from agent_os.execution.lock_manager import FileLockManager
                lock_manager = self._engine.registry.resolve(FileLockManager)
            except Exception:
                pass
        if lock_manager:
            self._release_all_locks(lock_manager)

        self._backups.clear()
        self._updates.clear()
        self._active = False


class TransactionalExecutionEngine(ITransactionalExecutionEngine):
    """Execution engine coordinating transactions, syntax validation AST, and conflicts."""
    def __init__(self, registry: Any | None = None) -> None:
        self.registry = registry

    def create_transaction(self, agent_name: str = "default_agent") -> ITransaction:
        return FileTransaction(self, agent_name)

    def validate_patch(self, file_path: str, current_content: str, target_content: str, replacement_content: str) -> str:
        # 1. Merge Conflict check (check if target exists in current content)
        if target_content not in current_content:
            raise MergeConflictError(f"Merge conflict: Target text block not found in '{os.path.basename(file_path)}'.")

        # 2. Apply patch in-memory
        patched_code = current_content.replace(target_content, replacement_content, 1)

        # 3. Syntax validation for Python files
        if file_path.endswith(".py"):
            try:
                ast.parse(patched_code)
            except SyntaxError as e:
                raise PatchSyntaxError(f"Syntax validation failed for '{os.path.basename(file_path)}' at line {e.lineno}: {e.msg}")

        return patched_code
