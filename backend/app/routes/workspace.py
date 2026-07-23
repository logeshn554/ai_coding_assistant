import os
import time
import logging
import subprocess
from collections import Counter
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import workspace_state, permission_manager, config_manager

_SERVER_START_TIME = time.time()

logger = logging.getLogger("devpilot.routes.workspace")
router = APIRouter()

# In Docker mode, Windows drives are mounted here
HOST_DRIVES_ROOT = "/host"
DRIVE_MAP = {"c": "C:\\", "d": "D:\\", "e": "E:\\"}


class WorkspaceChangeRequest(BaseModel):
    path: str


@router.get("/api/workspace")
def get_workspace():
    return {"workspace": workspace_state.root}


@router.get("/api/shell/name")
def get_shell_name():
    from ..shell_adapter import ShellAdapter
    return {"name": ShellAdapter.get_shell_name()}


@router.post("/api/workspace/change")
def change_workspace(req: WorkspaceChangeRequest):
    try:
        raw_path = (req.path or "").strip().strip('"').strip("'")
        if raw_path == "":
            workspace_state.root = ""
            permission_manager.workspace_root = ""
            config_manager.set_last_workspace("")
            logger.info("Workspace closed.")
            return {"success": True, "workspace": ""}

        path = os.path.normpath(raw_path)

        # Handle Docker mode path translation
        if os.environ.get("DOCKER_MODE", "false").lower() == "true":
            norm = raw_path.replace("\\", "/").strip()
            import re
            match = re.match(r"^([A-Za-z]):(.*)", norm)
            if match:
                drive_letter = match.group(1).lower()
                subpath = match.group(2).lstrip("/")
                path = os.path.normpath(f"/host/{drive_letter}/{subpath}")
            elif not norm.startswith("/host") and not norm.startswith("/workspace") and not norm.startswith("/"):
                path = os.path.normpath(f"/workspace/{norm}")
            else:
                path = os.path.normpath(norm)
        else:
            path = os.path.abspath(path)

        if not os.path.isdir(path):
            raise HTTPException(
                status_code=400,
                detail=f"Directory does not exist: {path}"
            )

        workspace_state.root = path
        permission_manager.workspace_root = path
        logger.info(f"Workspace changed to: {workspace_state.root}")
        config_manager.set_last_workspace(workspace_state.root)
        return {"success": True, "workspace": workspace_state.root}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/workspace/browse")
def browse_workspace(path: str = ""):
    """
    Returns immediate subdirectories of the given path.
    - No path → returns the list of mounted Windows drives (/host/c, /host/d, /host/e)
    - With path → lists subdirectories inside that container path
    """
    is_docker = os.environ.get("DOCKER_MODE", "false").lower() == "true"

    # Root: show available drives
    if not path:
        if is_docker:
            drives = []
            for letter, win_label in DRIVE_MAP.items():
                mount = os.path.join(HOST_DRIVES_ROOT, letter)
                if os.path.isdir(mount):
                    drives.append({
                        "name": win_label,
                        "path": mount,
                        "is_dir": True,
                        "is_drive": True
                    })
            return {
                "current": "",
                "parent": None,
                "entries": drives,
                "is_docker": True,
                "is_root": True
            }
        else:
            browse_path = os.path.expanduser("~")
            return _list_dir(browse_path, parent=None, is_docker=False)

    browse_path = os.path.normpath(path)

    if not os.path.isdir(browse_path):
        raise HTTPException(status_code=404, detail=f"Path not found: {browse_path}")

    # Determine parent
    parent = os.path.dirname(browse_path)

    # If going up from a drive root (/host/c → /host/c itself), go to drive list instead
    if is_docker and browse_path in [os.path.join(HOST_DRIVES_ROOT, l) for l in DRIVE_MAP]:
        parent = None  # signals "go back to drive list"

    return _list_dir(browse_path, parent=parent, is_docker=is_docker)


def _list_dir(browse_path: str, parent, is_docker: bool):
    try:
        entries = []
        with os.scandir(browse_path) as it:
            for entry in sorted(it, key=lambda e: e.name.lower()):
                try:
                    if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                        entries.append({
                            "name": entry.name,
                            "path": entry.path,
                            "is_dir": True,
                            "is_drive": False
                        })
                except PermissionError:
                    pass

        return {
            "current": browse_path,
            "parent": parent,
            "entries": entries,
            "is_docker": is_docker,
            "is_root": False
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/workspace/select")
def select_workspace():
    """
    Tries to open the native OS folder picker.
    If unavailable (Docker/headless), signals the frontend to show the browser UI.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title="Select Workspace Folder")
        root.destroy()

        if folder_path:
            normalized = os.path.abspath(folder_path).replace("\\", "/")
            return {"path": normalized}
        return {"path": None, "cancelled": True}
    except Exception as e:
        logger.info(f"Native directory dialog unavailable ({e}).")
        return {"path": None, "dialog_unavailable": True}


# ── Extension → language display name map ────────────────────────────────────

_EXT_LANG_MAP = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".html": "HTML",
    ".css": "CSS", ".scss": "CSS", ".json": "JSON", ".yaml": "YAML",
    ".yml": "YAML", ".md": "Markdown", ".sh": "Shell",
    ".dockerfile": "Docker", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".cpp": "C++", ".c": "C", ".cs": "C#",
    ".rb": "Ruby", ".php": "PHP", ".kt": "Kotlin", ".swift": "Swift",
}

_SKIP_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".devpilot",
    "dist", "build", ".next", ".cache", ".pytest_cache",
}


@router.get("/api/workspace/stats")
def get_workspace_stats():
    """Returns real workspace statistics: file counts, language breakdown, git commit count."""
    root = workspace_state.root
    if not root or not os.path.isdir(root):
        return {
            "total_files": 0,
            "total_lines": 0,
            "languages": {},
            "git_commits": 0,
        }

    lang_counter: Counter = Counter()
    total_files = 0
    total_lines = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk won't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            lang = _EXT_LANG_MAP.get(ext)
            if not lang:
                continue
            total_files += 1
            lang_counter[lang] += 1
            # Count lines (best-effort, skip binary files)
            try:
                fpath = os.path.join(dirpath, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    total_lines += sum(1 for _ in fh)
            except Exception:
                pass

    # Build percentage map (relative to tracked files only)
    languages: dict = {}
    if lang_counter:
        grand_total = sum(lang_counter.values())
        languages = {
            lang: round((count / grand_total) * 100, 1)
            for lang, count in lang_counter.most_common(8)
        }

    # Git commit count
    git_commits = 0
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            git_commits = int(result.stdout.strip())
    except Exception:
        pass

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "languages": languages,
        "git_commits": git_commits,
    }


@router.get("/api/health")
async def get_health():
    """Returns server health status, uptime, and Redis connectivity."""
    from pathlib import Path as _Path
    from ..state import redis_client

    db_file = _Path.home() / ".devpilot" / "history.db"
    db_connected = db_file.exists()
    uptime = round(time.time() - _SERVER_START_TIME, 1)

    redis_connected = False
    try:
        redis_connected = bool(await redis_client.ping())
    except Exception as exc:
        logger.warning("Health Redis probe failed: %s", exc)
        redis_connected = False

    return {
        "status": "ok",
        "db_connected": db_connected,
        "redis_connected": redis_connected,
        "uptime_seconds": uptime,
    }

