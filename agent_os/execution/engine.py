import os
import ast
import tempfile
from typing import Any, Dict, List
from agent_os.execution.interfaces import ITransactionalExecutionEngine, ITransaction

class MergeConflictError(Exception):
    pass

class PatchSyntaxError(Exception):
    pass

class TransactionError(Exception):
    pass


class FileTransaction(ITransaction):
    """File modification transaction mapping target files to in-memory buffers before committing."""
    def __init__(self, engine: "TransactionalExecutionEngine") -> None:
        self._engine = engine
        self._backups: Dict[str, str] = {}
        self._updates: Dict[str, str] = {}
        self._active = False

    def begin(self) -> None:
        self._backups.clear()
        self._updates.clear()
        self._active = True

    def apply_patch(self, file_path: str, target_content: str, replacement_content: str) -> None:
        if not self._active:
            raise TransactionError("Transaction is not active. Call begin() first.")

        # Determine current content state
        if file_path in self._updates:
            current_content = self._updates[file_path]
        else:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Target file '{file_path}' does not exist.")
            with open(file_path, "r", encoding="utf-8") as f:
                current_content = f.read()
            self._backups[file_path] = current_content

        # Validate and compile patch
        patched_code = self._engine.validate_patch(
            file_path, current_content, target_content, replacement_content
        )
        self._updates[file_path] = patched_code

    def commit(self) -> None:
        if not self._active:
            raise TransactionError("Transaction is not active.")

        committed_files: List[str] = []
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
            raise TransactionError(f"Commit failed. Rolled back committed changes. Error: {str(e)}")

        self._active = False

    def rollback(self) -> None:
        self._backups.clear()
        self._updates.clear()
        self._active = False


class TransactionalExecutionEngine(ITransactionalExecutionEngine):
    """Execution engine coordinating transactions, syntax validation AST, and conflicts."""
    def create_transaction(self) -> ITransaction:
        return FileTransaction(self)

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
