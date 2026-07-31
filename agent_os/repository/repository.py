import os
import hashlib
from typing import Any, List, Dict
from agent_os.repository.interfaces import IRepository
from agent_os.repository.db import DatabaseManager
from agent_os.repository.parser import detect_language, parse_code

class RepositoryKernel(IRepository):
    """Concrete Repository Kernel scanning the workspace and storing metadata in SQLite."""
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db = DatabaseManager(db_path)
        self.workspace_root = ""

    def read_file(self, path: str) -> str:
        full_path = os.path.join(self.workspace_root, path) if self.workspace_root else path
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        full_path = os.path.join(self.workspace_root, path) if self.workspace_root else path
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_files(self) -> List[str]:
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
        self.workspace_root = workspace_root
        
        for root, dirs, filenames in os.walk(workspace_root):
            # Ignore standard directories
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "dist", "build", "target", "__pycache__", "venv", ".venv", "env", ".env"}]
            
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")
                
                try:
                    size = os.path.getsize(full_path)
                    mtime = int(os.path.getmtime(full_path))
                    
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        
                    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    language = detect_language(rel_path)
                    
                    self.db.clear_file_metadata(rel_path)
                    file_id = self.db.insert_file(rel_path, language, size, mtime, content_hash)
                    
                    symbols, references = parse_code(content, language)
                    
                    for sym in symbols:
                        self.db.insert_symbol(
                            file_id=file_id,
                            name=sym.name,
                            sym_type=sym.sym_type,
                            start_line=sym.start_line,
                            start_col=sym.start_col,
                            end_line=sym.end_line,
                            end_col=sym.end_col,
                            signature=sym.signature
                        )
                        
                    for ref in references:
                        self.db.insert_reference(
                            file_id=file_id,
                            symbol_name=ref.name,
                            line=ref.line,
                            col=ref.col
                        )
                except Exception:
                    pass

    def find_file(self, pattern: str) -> List[Dict[str, Any]]:
        return self.db.query_files(pattern)

    def find_function(self, name: str) -> List[Dict[str, Any]]:
        return self.db.query_symbols(name, "function")

    def find_class(self, name: str) -> List[Dict[str, Any]]:
        return self.db.query_symbols(name, "class")

    def find_references(self, symbol: str) -> List[Dict[str, Any]]:
        return self.db.query_references(symbol)
