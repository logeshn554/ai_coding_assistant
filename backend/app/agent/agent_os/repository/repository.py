import asyncio
import concurrent.futures
import hashlib
import os
from typing import Any

from agent_os.repository.db import DatabaseManager
from agent_os.repository.interfaces import IRepository
from agent_os.repository.parser import detect_language, parse_code


class RepositoryKernel(IRepository):
    """Concrete Repository Kernel scanning the workspace and storing metadata in SQLite."""
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db = DatabaseManager(db_path)
        self.workspace_root = ""

    def read_file(self, path: str) -> str:
        from agent_os.repository.file_operations import FileOperations
        ops = FileOperations(self.workspace_root)
        result = ops.read_file(path)
        if not result.success:
            raise FileNotFoundError(result.message)
        return result.content or ""

    def write_file(self, path: str, content: str) -> None:
        from agent_os.repository.file_operations import FileOperations
        ops = FileOperations(self.workspace_root)
        result = ops.write_file(path, content)
        if not result.success:
            raise OSError(result.message)

    def create_file(self, file_path: str, content: str = "") -> bool:
        from agent_os.repository.file_operations import FileOperations
        ops = FileOperations(self.workspace_root)
        result = ops.create_file(file_path, content)
        return result.success

    def edit_file(self, file_path: str, target: str, replacement: str) -> bool:
        from agent_os.repository.file_operations import FileOperations
        ops = FileOperations(self.workspace_root)
        result = ops.edit_file(file_path, target, replacement)
        return result.success

    def list_files(self) -> list[str]:
        if not self.workspace_root:
            return []
        files = []
        for root, dirs, filenames in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "dist", "build", "target", "__pycache__"}]
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), self.workspace_root).replace("\\", "/")
                files.append(rel)
        return files

    def scan_workspace(self, workspace_root: str) -> None:
        self.scan_workspace_sync(workspace_root)

    def scan_workspace_sync(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        
        # 1. Query all existing files from DB to build mtimes mapping
        db_files = self.db.query_files("")
        db_mtimes = {f["path"]: (f["modified_time"], f["id"]) for f in db_files}
        
        # 2. Collect all files in workspace root
        all_paths = []
        for root, dirs, filenames in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "dist", "build", "target", "__pycache__", "venv", ".venv", "env", ".env"}]
            for f in filenames:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")
                all_paths.append((full_path, rel_path))
                
        # 3. Use ThreadPoolExecutor to parse and insert files in parallel
        def _index_file(full_path: str, rel_path: str) -> None:
            try:
                size = os.path.getsize(full_path)
                mtime = int(os.path.getmtime(full_path))
                
                # Check incremental cache
                if rel_path in db_mtimes:
                    cached_mtime, file_id = db_mtimes[rel_path]
                    if mtime == cached_mtime:
                        # File hasn't changed, skip parsing!
                        return
                
                # Read & parse
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                language = detect_language(rel_path)
                
                # Clear and insert (cascade delete takes care of old symbols/refs)
                self.db.clear_file_metadata(rel_path)
                file_id = self.db.insert_file(rel_path, language, size, mtime, content_hash)
                
                symbols, references = parse_code(content, language)
                
                self.db.insert_symbols_batch(file_id, symbols)
                self.db.insert_references_batch(file_id, references)
            except Exception:
                pass

        # Run in parallel thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_index_file, fp, rp) for fp, rp in all_paths]
            concurrent.futures.wait(futures)
            
        # 4. Clean up deleted/stale records from DB
        scanned_paths = {rp for _, rp in all_paths}
        for path in db_mtimes:
            if path not in scanned_paths:
                self.db.clear_file_metadata(path)

    async def scan_workspace_parallel(self, workspace_root: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.scan_workspace_sync, workspace_root)

    def find_file(self, pattern: str) -> list[dict[str, Any]]:
        return self.db.query_files(pattern)

    def find_function(self, name: str) -> list[dict[str, Any]]:
        return self.db.query_symbols(name, "function")

    def find_class(self, name: str) -> list[dict[str, Any]]:
        return self.db.query_symbols(name, "class")

    def find_references(self, symbol: str) -> list[dict[str, Any]]:
        return self.db.query_references(symbol)

    def store_lsp_diagnostics(self, path: str, diagnostics: list[dict[str, Any]]) -> None:
        """Stores active LSP diagnostics for the given relative file path in the repository database."""
        files = self.db.query_files(path)
        if not files:
            return
        file_id = files[0]["id"]
        self.db.clear_diagnostics(file_id)
        for diag in diagnostics:
            self.db.insert_diagnostic(
                file_id=file_id,
                message=diag.get("message", ""),
                severity=diag.get("severity", 1),
                line=diag.get("line", 0),
                character=diag.get("character", 0),
                code=diag.get("code"),
                source=diag.get("source", "LSP")
            )

    def get_lsp_diagnostics(self, path: str) -> list[dict[str, Any]]:
        return self.db.query_diagnostics_for_file(path)

    def get_symbol_diagnostics(self, symbol_name: str) -> list[dict[str, Any]]:
        return self.db.query_diagnostics_for_symbol(symbol_name)
