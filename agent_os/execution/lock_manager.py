import hashlib
import os
import threading
from typing import Dict, List, Tuple
from agent_os.execution.interfaces import IFileLockManager

class FileLockManager(IFileLockManager):
    """Coordinates file access and prevents concurrent modifications.

    All lock operations are serialized through a threading.RLock to prevent
    TOCTOU races when multiple parallel agents attempt to acquire or release
    locks on the same file simultaneously.
    """
    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Structure: {file_path: (holder_agent_name, exclusive_flag)}
        self._locks: Dict[str, Tuple[str, bool]] = {}
        # Structure: {file_path: (hash_str, mtime_float)} for optimistic locking
        self._file_snapshots: Dict[str, Tuple[str, float]] = {}

    def acquire_lock(self, file_path: str, agent_name: str, exclusive: bool = True) -> bool:
        normalized_path = os.path.normpath(file_path).replace("\\", "/")

        with self._lock:
            # Check existing locks — check+acquire is atomic under the lock
            if normalized_path in self._locks:
                holder, is_exclusive = self._locks[normalized_path]
                if holder == agent_name:
                    # Agent already owns a lock; upgrade to exclusive if requested
                    if exclusive and not is_exclusive:
                        self._locks[normalized_path] = (agent_name, True)
                    return True
                # Shared locks can coexist if neither is exclusive
                if not exclusive and not is_exclusive:
                    return True
                return False

            self._locks[normalized_path] = (agent_name, exclusive)
            return True

    def release_lock(self, file_path: str, agent_name: str) -> bool:
        normalized_path = os.path.normpath(file_path).replace("\\", "/")
        with self._lock:
            if normalized_path in self._locks:
                holder, _ = self._locks[normalized_path]
                if holder == agent_name:
                    del self._locks[normalized_path]
                    return True
            return False

    def is_locked(self, file_path: str) -> bool:
        normalized_path = os.path.normpath(file_path).replace("\\", "/")
        with self._lock:
            return normalized_path in self._locks

    def get_all_locks(self) -> Dict[str, Tuple[str, bool]]:
        """Return a snapshot of all current locks (for diagnostics)."""
        with self._lock:
            return dict(self._locks)

    # Optimistic locking methods
    def snapshot_file(self, file_path: str) -> None:
        normalized_path = os.path.normpath(file_path).replace("\\", "/")
        if not os.path.exists(file_path):
            with self._lock:
                self._file_snapshots.pop(normalized_path, None)
            return

        try:
            mtime = os.path.getmtime(file_path)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
            with self._lock:
                self._file_snapshots[normalized_path] = (h, mtime)
        except Exception:
            pass

    def verify_optimistic_lock(self, file_path: str) -> bool:
        normalized_path = os.path.normpath(file_path).replace("\\", "/")
        with self._lock:
            if normalized_path not in self._file_snapshots:
                return True  # No snapshot taken, succeed optimistic check
            snap_hash, snap_mtime = self._file_snapshots[normalized_path]

        if not os.path.exists(file_path):
            return False  # File was deleted since snapshot

        try:
            mtime = os.path.getmtime(file_path)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
            return h == snap_hash or mtime == snap_mtime
        except Exception:
            return False
