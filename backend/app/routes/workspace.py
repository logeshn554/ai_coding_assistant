import asyncio
import datetime
import logging
import os
import subprocess
import time
from collections import Counter

from fastapi import APIRouter, HTTPException

from ..schemas.workspace import (
    DetectCommandRequest,
    DetectCommandResponse,
    HealthCheckResponse,
    RootsAddResponse,
    RootsResponse,
    ShellNameResponse,
    SSHHostRequest,
    SSHHostResponse,
    SSHHostsResponse,
    WorkspaceChangeRequest,
    WorkspaceChangeResponse,
    WorkspaceInfoResponse,
    WorkspaceStatsResponse,
)
from ..state import config_manager, get_permission_manager, workspace_state

_SERVER_START_TIME = time.time()

logger = logging.getLogger("devpilot.routes.workspace")
router = APIRouter()

# In Docker mode, Windows drives are mounted here
HOST_DRIVES_ROOT = "/host"
DRIVE_MAP = {"c": "C:\\", "d": "D:\\", "e": "E:\\"}


@router.get("/api/workspace", response_model=WorkspaceInfoResponse)
async def get_workspace():
    return {"workspace": workspace_state.root}


@router.post("/api/workspace/detect-file-command", response_model=DetectCommandResponse)
async def detect_file_command(req: DetectCommandRequest):
    """
    Asks the LLM to dynamically determine the appropriate execution command for a file,
    eliminating static hardcoded command maps.
    """
    file_path = (req.file_path or "").strip()
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path cannot be empty")

    norm_path = file_path.replace("\\", "/")

    try:
        profile = config_manager.get_active_profile()
        if profile and (profile.get("api_key") or "localhost" in profile.get("base_url", "")):
            from ..adapters.router import ModelRouter
            router_inst = ModelRouter()
            sys_prompt = (
                "You are an AI CLI command detector for a software IDE. "
                "Given a file path in a repository, return ONLY the single, exact shell command line to run or execute that file. "
                "Do NOT use markdown code blocks, backticks, quotes around the whole line, or extra explanation text. "
                "Output ONLY the raw command string."
            )
            messages = [{"role": "user", "content": f"File path to execute: {norm_path}"}]
            llm_cmd = await router_inst.completion(profile, messages, system_prompt=sys_prompt)
            clean_cmd = llm_cmd.strip().strip("`").strip('"').strip("'").strip()
            if clean_cmd.startswith("```"):
                lines = [l for l in clean_cmd.splitlines() if not l.startswith("```")]
                clean_cmd = " ".join(lines).strip()
            if clean_cmd:
                return {"command": clean_cmd}
    except Exception as e:
        logger.warning(f"LLM command detection fallback for {norm_path}: {e}")

    ext = norm_path.split(".")[-1].lower() if "." in norm_path else ""
    return {"command": f"{ext} \"{norm_path}\"" if ext else f"\"{norm_path}\""}


@router.get("/api/shell/name", response_model=ShellNameResponse)
async def get_shell_name():
    from ..shell_adapter import ShellAdapter
    return {"name": ShellAdapter.get_shell_name()}


from pathlib import Path


def validate_workspace_path(path_str: str) -> str:
    """
    Canonical validator for workspace paths.
    Enforces strict Path.is_relative_to containment in production server mode.
    """
    from backend.app.config import settings
    candidate = Path(path_str).resolve()

    env_mode = os.getenv("ENVIRONMENT", settings.ENVIRONMENT)
    server_mode = os.getenv("MODE", settings.MODE)

    if env_mode == "production" and server_mode == "server":
        allowed_base = Path(os.getenv("TENANT_WORKSPACES_ROOT", "/srv/devpilot/workspaces")).resolve()
        try:
            if not candidate.is_relative_to(allowed_base):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access Denied: In production multi-tenant mode, workspaces must reside within {allowed_base}"
                )
        except AttributeError:
            # Fallback for Python < 3.9 if any
            try:
                candidate.relative_to(allowed_base)
            except ValueError:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access Denied: In production multi-tenant mode, workspaces must reside within {allowed_base}"
                )

    return str(candidate)


@router.post("/api/workspace/change", response_model=WorkspaceChangeResponse)
async def change_workspace(req: WorkspaceChangeRequest):
    try:
        raw_path = (req.path or "").strip().strip('"').strip("'")
        if raw_path == "":
            workspace_state.root = ""
            get_permission_manager().workspace_root = ""
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

        validated_path = validate_workspace_path(path)

        is_dir = await asyncio.to_thread(os.path.isdir, validated_path)
        if not is_dir:
            raise HTTPException(
                status_code=400,
                detail=f"Directory does not exist: {validated_path}"
            )

        workspace_state.root = validated_path
        get_permission_manager().workspace_root = validated_path
        logger.info(f"Workspace changed to: {workspace_state.root}")
        config_manager.set_last_workspace(workspace_state.root)
        return {"success": True, "workspace": workspace_state.root}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/api/workspace/browse")
async def browse_workspace(path: str = ""):
    """
    Returns immediate subdirectories of the given path.
    - Server / Production Mode: Restricts root and navigation strictly to TENANT_WORKSPACES_ROOT.
    - Desktop Mode: Lists available mounted drives or user home directory.
    """
    from backend.app.config import settings
    is_prod_server = (settings.ENVIRONMENT == "production" and settings.MODE == "server")
    is_docker = os.environ.get("DOCKER_MODE", "false").lower() == "true"

    if is_prod_server:
        tenant_base = Path(os.getenv("TENANT_WORKSPACES_ROOT", "/srv/devpilot/workspaces")).resolve()
        if not path:
            browse_path = str(tenant_base)
            parent = None
        else:
            validated_path = validate_workspace_path(path)
            browse_path = validated_path
            parent = str(Path(browse_path).parent) if Path(browse_path) != tenant_base else None

        return await asyncio.to_thread(_list_dir, browse_path, parent=parent, is_docker=False)

    # Desktop / local development mode
    if not path:
        if is_docker:
            drives = []
            for letter, win_label in DRIVE_MAP.items():
                mount = os.path.join(HOST_DRIVES_ROOT, letter)
                is_mount_dir = await asyncio.to_thread(os.path.isdir, mount)
                if is_mount_dir:
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
            browse_path = await asyncio.to_thread(os.path.expanduser, "~")
            return await asyncio.to_thread(_list_dir, browse_path, parent=None, is_docker=False)

    browse_path = os.path.normpath(path)
    is_dir = await asyncio.to_thread(os.path.isdir, browse_path)
    if not is_dir:
        raise HTTPException(status_code=404, detail=f"Path not found: {browse_path}")

    parent = os.path.dirname(browse_path)
    if is_docker and browse_path in [os.path.join(HOST_DRIVES_ROOT, l) for l in DRIVE_MAP]:
        parent = None

    return await asyncio.to_thread(_list_dir, browse_path, parent=parent, is_docker=is_docker)


@router.post("/api/workspace/select")
async def select_workspace():
    """
    Tries to open the native OS folder picker in a background thread.
    If unavailable (Docker/headless), signals the frontend to show the browser UI.
    """
    def _pick_directory():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title="Select Workspace Folder")
        root.destroy()
        return folder_path

    try:
        folder_path = await asyncio.to_thread(_pick_directory)
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


def _get_stats_sync(root: str) -> dict:
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
    languages = {}
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


from ..cache import cached


@cached(ttl=60)
async def _get_cached_stats(root: str) -> dict:
    return await asyncio.to_thread(_get_stats_sync, root)

@router.get("/api/workspace/stats", response_model=WorkspaceStatsResponse)
async def get_workspace_stats():
    """Returns real workspace statistics: file counts, language breakdown, git commit count."""
    root = workspace_state.root
    is_dir = await asyncio.to_thread(os.path.isdir, root) if root else False
    if not root or not is_dir:
        return {
            "total_files": 0,
            "total_lines": 0,
            "languages": {},
            "git_commits": 0,
        }

    return await _get_cached_stats(root=root)


_MULTI_ROOTS: list[str] = []
_SSH_HOSTS: list[dict] = []


@router.get("/api/workspace/roots", response_model=RootsResponse)
async def get_workspace_roots():
    """Returns active multi-root workspace folders."""
    roots = [workspace_state.root] if workspace_state.root else []
    for r in _MULTI_ROOTS:
        is_dir = await asyncio.to_thread(os.path.isdir, r)
        if r and r not in roots and is_dir:
            roots.append(r)
    return {"roots": roots, "active_root": workspace_state.root}


@router.post("/api/workspace/roots/add", response_model=RootsAddResponse)
async def add_workspace_root(req: WorkspaceChangeRequest):
    """Adds a secondary root folder to the multi-root workspace."""
    path = os.path.normpath(req.path or "")
    validated_path = validate_workspace_path(path)
    is_dir = await asyncio.to_thread(os.path.isdir, validated_path)
    if not is_dir:
        raise HTTPException(status_code=400, detail="Folder path does not exist")
    if validated_path not in _MULTI_ROOTS:
        _MULTI_ROOTS.append(validated_path)
    roots_info = await get_workspace_roots()
    return {"success": True, "roots": roots_info["roots"]}


@router.get("/api/workspace/ssh-hosts", response_model=SSHHostsResponse)
async def get_ssh_hosts():
    """Returns configured Remote SSH Host profiles."""
    return {"hosts": _SSH_HOSTS}


@router.post("/api/workspace/ssh-hosts", response_model=SSHHostResponse)
async def add_ssh_host(req: SSHHostRequest):
    """Adds or tests a Remote SSH Host profile."""
    profile = {"name": req.name, "host": req.host, "username": req.username, "port": req.port}
    _SSH_HOSTS.append(profile)
    return {"success": True, "host": profile}


@router.get("/api/health", response_model=HealthCheckResponse)
async def get_health():
    """Returns server health status, uptime, and Redis connectivity."""
    from pathlib import Path as _Path

    from ..state import redis_client

    db_file = _Path.home() / ".devpilot" / "history.db"
    db_connected = await asyncio.to_thread(db_file.exists)
    uptime = round(time.time() - _SERVER_START_TIME, 1)

    redis_connected = False
    try:
        redis_connected = bool(await redis_client.ping())
    except Exception as exc:
        logger.warning("Health Redis probe failed: %s", exc)
        redis_connected = False

    # Get version from environment
    version = os.environ.get("DEVPILOT_VERSION", "0.1.0")

    return {
        "status": "healthy",
        "version": version,
        "db_connected": db_connected,
        "redis_connected": redis_connected,
        "uptime_seconds": uptime,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
