import os
import sqlite3
import threading
from typing import Any, Dict, List

class DatabaseManager:
    """SQLite Database manager handling repository metadata storage and symbol queries."""
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._local = threading.local()
        # Initialize connection for the main thread first to set up the DB
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            if self.db_path == ":memory:":
                conn = sqlite3.connect("file::memory:?cache=shared", uri=True, check_same_thread=False)
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            if self.db_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA cache_size = -32000;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        path TEXT UNIQUE,
                        language TEXT,
                        size_bytes INTEGER,
                        modified_time INTEGER,
                        content_hash TEXT
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS symbols (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id INTEGER,
                        name TEXT,
                        type TEXT, -- 'class', 'function', 'import', 'export'
                        start_line INTEGER,
                        start_col INTEGER,
                        end_line INTEGER,
                        end_col INTEGER,
                        signature TEXT,
                        FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_references (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id INTEGER,
                        symbol_name TEXT,
                        line INTEGER,
                        col INTEGER,
                        FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lsp_diagnostics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id INTEGER,
                        message TEXT,
                        severity INTEGER,
                        line INTEGER,
                        character INTEGER,
                        code TEXT,
                        source TEXT,
                        FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
                    );
                """)
                # Indexes for O(1) matching speedups
                conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_references_name ON symbol_references(symbol_name);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);")

    def clear_file_metadata(self, path: str) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM files WHERE path = ?;", (path,))

    def insert_file(self, path: str, language: str, size: int, mtime: int, content_hash: str) -> int:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO files (path, language, size_bytes, modified_time, content_hash)
                    VALUES (?, ?, ?, ?, ?);
                """, (path, language, size, mtime, content_hash))
                return cursor.lastrowid

    def insert_symbol(self, file_id: int, name: str, sym_type: str, start_line: int, start_col: int, end_line: int, end_col: int, signature: str = "") -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO symbols (file_id, name, type, start_line, start_col, end_line, end_col, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (file_id, name, sym_type, start_line, start_col, end_line, end_col, signature))

    def insert_symbols_batch(self, file_id: int, symbols: List[Any]) -> None:
        """Batch insert symbol objects."""
        if not symbols:
            return
        data = []
        for sym in symbols:
            if hasattr(sym, "name"):
                data.append((
                    file_id, sym.name, sym.sym_type, sym.start_line, sym.start_col, sym.end_line, sym.end_col, sym.signature
                ))
            elif isinstance(sym, dict):
                data.append((
                    file_id, sym.get("name"), sym.get("type"), sym.get("start_line"), sym.get("start_col"), sym.get("end_line"), sym.get("end_col"), sym.get("signature", "")
                ))
            else:
                data.append(sym)

        with self._lock:
            with self._get_connection() as conn:
                conn.executemany("""
                    INSERT INTO symbols (file_id, name, type, start_line, start_col, end_line, end_col, signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, data)

    def insert_reference(self, file_id: int, symbol_name: str, line: int, col: int) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO symbol_references (file_id, symbol_name, line, col)
                    VALUES (?, ?, ?, ?);
                """, (file_id, symbol_name, line, col))

    def insert_references_batch(self, file_id: int, references: List[Any]) -> None:
        """Batch insert reference objects."""
        if not references:
            return
        data = []
        for ref in references:
            if hasattr(ref, "name"):
                data.append((file_id, ref.name, ref.line, ref.col))
            elif isinstance(ref, dict):
                data.append((file_id, ref.get("name"), ref.get("line"), ref.get("col")))
            else:
                data.append(ref)

        with self._lock:
            with self._get_connection() as conn:
                conn.executemany("""
                    INSERT INTO symbol_references (file_id, symbol_name, line, col)
                    VALUES (?, ?, ?, ?);
                """, data)

    def query_files(self, pattern: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute("SELECT * FROM files WHERE path LIKE ?;", (f"%{pattern}%",)).fetchall()
        return [dict(r) for r in rows]

    def query_symbols(self, name: str, sym_type: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute("""
            SELECT s.*, f.path as file_path, f.language
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.name = ? AND s.type = ?;
        """, (name, sym_type)).fetchall()
        return [dict(r) for r in rows]

    def query_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute("""
            SELECT r.*, f.path as file_path
            FROM symbol_references r
            JOIN files f ON r.file_id = f.id
            WHERE r.symbol_name = ?;
        """, (symbol_name,)).fetchall()
        return [dict(r) for r in rows]

    def clear_diagnostics(self, file_id: int) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM lsp_diagnostics WHERE file_id = ?;", (file_id,))

    def insert_diagnostic(self, file_id: int, message: str, severity: int, line: int, character: int, code: str = None, source: str = "LSP") -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO lsp_diagnostics (file_id, message, severity, line, character, code, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (file_id, message, severity, line, character, code, source))

    def query_diagnostics_for_file(self, file_path: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute("""
            SELECT d.*, f.path as file_path
            FROM lsp_diagnostics d
            JOIN files f ON d.file_id = f.id
            WHERE f.path = ?;
        """, (file_path,)).fetchall()
        return [dict(r) for r in rows]

    def query_diagnostics_for_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        symbol_rows = conn.execute("""
            SELECT s.file_id, s.start_line, s.end_line, f.path as file_path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.name = ?;
        """, (symbol_name,)).fetchall()
        
        all_diagnostics = []
        for s_row in symbol_rows:
            file_id = s_row["file_id"]
            start_line = s_row["start_line"]
            end_line = s_row["end_line"]
            file_path = s_row["file_path"]
            
            diag_rows = conn.execute("""
                SELECT d.*, ? as file_path
                FROM lsp_diagnostics d
                WHERE d.file_id = ? AND d.line >= ? AND d.line <= ?;
            """, (file_path, file_id, start_line, end_line)).fetchall()
            all_diagnostics.extend([dict(r) for r in diag_rows])
        return all_diagnostics
