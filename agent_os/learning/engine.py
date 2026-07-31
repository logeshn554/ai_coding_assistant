import re
import json
import sqlite3
import os
import threading
import time
from typing import Any, Dict, List
from agent_os.learning.interfaces import ILearningEngine

class LearningEngine(ILearningEngine):
    """SQLite-backed structured learning engine with ChromaDB embedding similarity and Jaccard fallback."""
    
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_chroma_collection(self, name: str):
        # Ephemeral test database should not persist files in directory to maintain test isolation
        if self.db_path == ":memory:":
            return None
        try:
            import chromadb
            # Put Chroma next to SQLite DB
            chroma_dir = os.path.join(os.path.dirname(self.db_path), "chroma")
            os.makedirs(chroma_dir, exist_ok=True)
            client = chromadb.PersistentClient(path=chroma_dir)
            return client.get_or_create_collection(name=name)
        except Exception:
            return None

    def _init_db(self) -> None:
        with self._lock:
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
        with self._lock:
            with self._conn:
                self._conn.execute("""
                    INSERT INTO successful_fixes (error_type, file_path, error_msg, solution_diff)
                    VALUES (?, ?, ?, ?);
                """, (error_type, file_path, error_msg, solution_diff))
                
        # Index in Chroma DB
        col = self._get_chroma_collection("successful_fixes")
        if col:
            try:
                text_to_embed = f"{error_type} {error_msg}"
                doc_id = f"fix_{int(time.time())}_{hash(solution_diff)}"
                col.add(
                    documents=[text_to_embed],
                    metadatas=[{"file_path": file_path, "solution_diff": solution_diff, "error_type": error_type, "error_msg": error_msg}],
                    ids=[doc_id]
                )
            except Exception:
                pass

    def store_summary(self, repo_path: str, summary: Dict[str, Any]) -> None:
        summary_str = json.dumps(summary, ensure_ascii=False)
        with self._lock:
            with self._conn:
                self._conn.execute("""
                    INSERT OR REPLACE INTO repo_summaries (repo_path, summary_json)
                    VALUES (?, ?);
                """, (repo_path, summary_str))

    def store_pattern(self, pattern_name: str, pattern_type: str, code_snippet: str) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute("""
                    INSERT OR REPLACE INTO patterns (pattern_name, pattern_type, code_snippet)
                    VALUES (?, ?, ?);
                """, (pattern_name, pattern_type, code_snippet))
                
        # Index in Chroma DB
        col = self._get_chroma_collection("patterns")
        if col:
            try:
                text_to_embed = f"{pattern_name} {pattern_type}"
                doc_id = f"pat_{int(time.time())}_{hash(code_snippet)}"
                col.add(
                    documents=[text_to_embed],
                    metadatas=[{"pattern_name": pattern_name, "pattern_type": pattern_type, "code_snippet": code_snippet}],
                    ids=[doc_id]
                )
            except Exception:
                pass

    def store_convention(self, convention_name: str, rule: str) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute("""
                    INSERT OR REPLACE INTO conventions (convention_name, rule)
                    VALUES (?, ?);
                """, (convention_name, rule))

    def store_performance(self, operation: str, duration_sec: float, token_count: int) -> None:
        with self._lock:
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
        # Attempt Chroma retrieval
        col = self._get_chroma_collection("successful_fixes")
        if col:
            try:
                count = col.count()
                if count > 0:
                    results = col.query(query_texts=[query], n_results=min(5, count))
                    matches = []
                    if results and "documents" in results and results["documents"]:
                        docs = results["documents"][0]
                        metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                        distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
                        for meta, dist in zip(metas, distances):
                            score = round(1.0 - dist, 4)
                            if score >= 0.35:
                                matches.append({
                                    "error_type": meta.get("error_type", ""),
                                    "file_path": meta.get("file_path", ""),
                                    "error_msg": meta.get("error_msg", ""),
                                    "solution_diff": meta.get("solution_diff", ""),
                                    "similarity_score": score
                                })
                        if matches:
                            return matches
            except Exception:
                pass

        # SQLite/Jaccard Fallback
        with self._lock:
            rows = self._conn.execute("SELECT * FROM successful_fixes;").fetchall()
        matches = []
        for r in rows:
            fix_dict = dict(r)
            match_text = f"{fix_dict['error_type']} {fix_dict['error_msg']}"
            score = self._jaccard_similarity(query, match_text)
            if score > 0:
                fix_dict["similarity_score"] = score
                matches.append(fix_dict)
                
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        return matches

    def find_similar_patterns(self, query: str) -> List[Dict[str, Any]]:
        # Attempt Chroma retrieval
        col = self._get_chroma_collection("patterns")
        if col:
            try:
                count = col.count()
                if count > 0:
                    results = col.query(query_texts=[query], n_results=min(5, count))
                    matches = []
                    if results and "documents" in results and results["documents"]:
                        docs = results["documents"][0]
                        metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                        distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
                        for meta, dist in zip(metas, distances):
                            score = round(1.0 - dist, 4)
                            if score >= 0.35:
                                matches.append({
                                    "pattern_name": meta.get("pattern_name", ""),
                                    "pattern_type": meta.get("pattern_type", ""),
                                    "code_snippet": meta.get("code_snippet", ""),
                                    "similarity_score": score
                                })
                        if matches:
                            return matches
            except Exception:
                pass

        # SQLite/Jaccard Fallback
        with self._lock:
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
