import sqlite3
import threading
from typing import Any, Dict, List

class DatabaseManager:
    """SQLite Database manager handling repository metadata storage and symbol queries."""
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
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

    def insert_reference(self, file_id: int, symbol_name: str, line: int, col: int) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO symbol_references (file_id, symbol_name, line, col)
                    VALUES (?, ?, ?, ?);
                """, (file_id, symbol_name, line, col))

    def query_files(self, pattern: str) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT * FROM files WHERE path LIKE ?;", (f"%{pattern}%",)).fetchall()
                return [dict(r) for r in rows]

    def query_symbols(self, name: str, sym_type: str) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT s.*, f.path as file_path, f.language
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.name = ? AND s.type = ?;
                """, (name, sym_type)).fetchall()
                return [dict(r) for r in rows]

    def query_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT r.*, f.path as file_path
                    FROM symbol_references r
                    JOIN files f ON r.file_id = f.id
                    WHERE r.symbol_name = ?;
                """, (symbol_name,)).fetchall()
                return [dict(r) for r in rows]
