"""Experience Database Service — Records bug resolutions, modified file patterns, and solution confidence scores."""
import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("devpilot.brain.experience_db")

class ExperienceDatabase:
    def __init__(self, storage_path: str = ""):
        if not storage_path:
            self.storage_path = os.path.expanduser("~/.devpilot/experience_db.json")
        else:
            self.storage_path = storage_path

    def _load_data(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.storage_path):
            # Seed with initial default data if it doesn't exist
            defaults = [
                {
                    "title": "Cross-platform path resolution bug",
                    "cause": "Windows backslash vs POSIX path escaping",
                    "solution": "Use normalize_path() with POSIX forward slashes",
                    "confidence": 0.99
                },
                {
                    "title": "API endpoint route mismatch",
                    "cause": "Caller used /api/files/write instead of /api/files/save",
                    "solution": "Added route aliases for both endpoints in FastAPI router",
                    "confidence": 0.98
                }
            ]
            self._save_data(defaults)
            return defaults
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load experience db: %s", e)
            return []

    def _save_data(self, data: List[Dict[str, Any]]):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.warning("Failed to save experience db: %s", e)

    def record_experience(self, bug_title: str, cause: str, solution: str, confidence: float = 0.95) -> Dict[str, Any]:
        """Record a resolution experience into the persistent knowledge store."""
        import datetime
        entry = {
            "title": bug_title,
            "cause": cause,
            "solution": solution,
            "confidence": confidence,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        data = self._load_data()
        data.append(entry)
        self._save_data(data)
        return {"status": "recorded", "experience": entry}

    def list_experiences(self) -> List[Dict[str, Any]]:
        """List experiences fetched dynamically from the database file."""
        return self._load_data()

experience_db = ExperienceDatabase()
