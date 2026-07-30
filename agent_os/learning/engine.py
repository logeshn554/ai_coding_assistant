import re
import json
import sqlite3
from typing import Any, Dict, List
from agent_os.learning.interfaces import ILearningEngine

class LearningEngine(ILearningEngine):
    """SQLite-backed structured learning engine with Jaccard overlap similarity search."""
    
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS successful_fixes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT,
                    file_path TEXT,
                    error_msg TEXT,
                    solution_diff TEXT
                );
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS repo_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_path TEXT UNIQUE,
                    summary_json TEXT
                );
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT UNIQUE,
                    pattern_type TEXT,
                    code_snippet TEXT
                );
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS conventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    convention_name TEXT UNIQUE,
                    rule TEXT
                );
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT,
                    duration_sec REAL,
                    token_count INTEGER
                );
            """)

    def store_fix(self, error_type: str, file_path: str, error_msg: str, solution_diff: str) -> None:
        with self._conn:
            self._conn.execute("""
                INSERT INTO successful_fixes (error_type, file_path, error_msg, solution_diff)
                VALUES (?, ?, ?, ?);
            """, (error_type, file_path, error_msg, solution_diff))

    def store_summary(self, repo_path: str, summary: Dict[str, Any]) -> None:
        summary_str = json.dumps(summary, ensure_ascii=False)
        with self._conn:
            self._conn.execute("""
                INSERT OR REPLACE INTO repo_summaries (repo_path, summary_json)
                VALUES (?, ?);
            """, (repo_path, summary_str))

    def store_pattern(self, pattern_name: str, pattern_type: str, code_snippet: str) -> None:
        with self._conn:
            self._conn.execute("""
                INSERT OR REPLACE INTO patterns (pattern_name, pattern_type, code_snippet)
                VALUES (?, ?, ?);
            """, (pattern_name, pattern_type, code_snippet))

    def store_convention(self, convention_name: str, rule: str) -> None:
        with self._conn:
            self._conn.execute("""
                INSERT OR REPLACE INTO conventions (convention_name, rule)
                VALUES (?, ?);
            """, (convention_name, rule))

    def store_performance(self, operation: str, duration_sec: float, token_count: int) -> None:
        with self._conn:
            self._conn.execute("""
                INSERT INTO performance_stats (operation, duration_sec, token_count)
                VALUES (?, ?, ?);
            """, (operation, duration_sec, token_count))

    def _jaccard_similarity(self, query: str, text: str) -> float:
        query_words = set(re.findall(r'\b[A-Za-z0-9_]+\b', query.lower()))
        text_words = set(re.findall(r'\b[A-Za-z0-9_]+\b', text.lower()))
        if not query_words:
            return 0.0
        intersection = query_words.intersection(text_words)
        return len(intersection) / len(query_words)

    def find_similar_fixes(self, query: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM successful_fixes;").fetchall()
        matches = []
        for r in rows:
            fix_dict = dict(r)
            # Check match against error_type and error_msg
            match_text = f"{fix_dict['error_type']} {fix_dict['error_msg']}"
            score = self._jaccard_similarity(query, match_text)
            if score > 0:
                fix_dict["similarity_score"] = score
                matches.append(fix_dict)
                
        # Sort by score descending
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        return matches

    def find_similar_patterns(self, query: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM patterns;").fetchall()
        matches = []
        for r in rows:
            pat_dict = dict(r)
            match_text = f"{pat_dict['pattern_name']} {pat_dict['pattern_type']}"
            score = self._jaccard_similarity(query, match_text)
            if score > 0:
                pat_dict["similarity_score"] = score
                matches.append(pat_dict)
                
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        return matches
