import os
import shutil
import json
import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import ConfigManager
from .files import (
    list_workspace_dir,
    read_workspace_file,
    write_workspace_file,
    delete_workspace_item,
    safe_path,
    search_workspace_codebase
)
from .terminal import TerminalManager
from .agent import AgentSession

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("devpilot.main")

# Initialize FastAPI
app = FastAPI(title="DevPilot Backend")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow frontend origin (e.g. localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Config Manager
config_manager = ConfigManager()

# Workspace directory definition
# Default to the persistent last workspace if set, otherwise start empty (to avoid showing internal editor files)
INITIAL_WORKSPACE_ROOT = config_manager.get_last_workspace() or ""

class WorkspaceState:
    def __init__(self, initial_root: str):
        self.root = initial_root

workspace_state = WorkspaceState(INITIAL_WORKSPACE_ROOT)
logger.info(f"DevPilot Workspace Root initialized at: {workspace_state.root or '<No workspace loaded>'}")

from .permissions import PermissionManager
permission_manager = PermissionManager(config_manager, workspace_state.root)

# --- Pydantic Models ---
class ProfileSaveRequest(BaseModel):
    id: Optional[str] = None
    name: str
    api_key: str
    base_url: str
    model_name: str
    api_format: str

class ProfileSelectRequest(BaseModel):
    id: str

class FileCreateRequest(BaseModel):
    path: str
    is_dir: bool

class FileSaveRequest(BaseModel):
    path: str
    content: str

class FileDeleteRequest(BaseModel):
    path: str

class WorkspaceChangeRequest(BaseModel):
    path: str

class ModelsFetchRequest(BaseModel):
    profile_id: Optional[str] = None
    api_key: str
    base_url: str
    api_format: str

# --- Permissions & Rollback API models ---
class PermissionGrantRequest(BaseModel):
    command: str
    scope: str

class PermissionRevokeRequest(BaseModel):
    command: str
    scope: str  # "session" or "project"

class GitActionRequest(BaseModel):
    action: str  # stage, unstage, commit, push, pull, checkout
    path: Optional[str] = None
    message: Optional[str] = None
    branch: Optional[str] = None

class PackageInstallRequest(BaseModel):
    name: str

class TestRunRequest(BaseModel):
    file: Optional[str] = None

class RollbackRequest(BaseModel):
    path: str
    timestamp: Optional[int] = None

class SettingsUpdateRequest(BaseModel):
    exclude_list: list
    auto_backup_enabled: bool
    agent_model_name: Optional[str] = ""

class FileRenameRequest(BaseModel):
    old_path: str
    new_path: str

class PackageUninstallRequest(BaseModel):
    name: str

class ExtensionActionRequest(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None

class ChatHistoryRequest(BaseModel):
    messages: list

# --- REST Endpoints ---

@app.get("/api/workspace")
def get_workspace():
    return {"workspace": workspace_state.root}

@app.post("/api/workspace/change")
def change_workspace(req: WorkspaceChangeRequest):
    try:
        if req.path == "":
            workspace_state.root = ""
            permission_manager.workspace_root = ""
            config_manager.set_last_workspace("")
            logger.info("Workspace closed.")
            return {"success": True, "workspace": ""}
            
        path = os.path.abspath(req.path)
        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail=f"Directory '{req.path}' does not exist.")
        workspace_state.root = path
        permission_manager.workspace_root = path
        logger.info(f"Workspace changed to: {workspace_state.root}")
        config_manager.set_last_workspace(workspace_state.root)
        return {"success": True, "workspace": workspace_state.root}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profiles")
def get_profiles():
    return config_manager.list_profiles(mask_keys=True)

@app.post("/api/profiles")
def save_profile(profile: ProfileSaveRequest):
    try:
        saved = config_manager.save_profile(profile.model_dump())
        return {"success": True, "profile": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profiles/active")
def set_active_profile(req: ProfileSelectRequest):
    try:
        config_manager.set_active_profile(req.id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str):
    try:
        config_manager.delete_profile(profile_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/models/fetch")
def fetch_available_models(req: ModelsFetchRequest):
    import urllib.request
    import urllib.error
    
    api_key = req.api_key.strip()
    if (not api_key or "•" in api_key or "..." in api_key or "*" in api_key) and req.profile_id:
        profiles = config_manager.list_profiles(mask_keys=False).get("profiles", [])
        matched = next((p for p in profiles if p.get("id") == req.profile_id), None)
        if matched:
            api_key = matched.get("api_key", "").strip()

    if not api_key:
        return {"success": False, "models": []}

    try:
        url = req.base_url.strip()
        if not url.endswith("/models"):
            url = url.rstrip("/") + "/models"
            
        if req.api_format == "openai":
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        else:  # anthropic
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }

        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                models = []
                if "data" in data and isinstance(data["data"], list):
                    models = [m.get("id") for m in data["data"] if m.get("id")]
                elif "models" in data and isinstance(data["models"], list):
                    models = [m.get("id") for m in data["models"] if m.get("id")]
                elif isinstance(data, list):
                    models = data
                
                models = sorted(list(set(filter(None, models))))
                return {"success": True, "models": models}
        except urllib.error.URLError as ue:
            logger.warning(f"Failed to fetch models from API: {str(ue)}")
            return {"success": False, "models": []}
    except Exception as e:
        logger.warning(f"Error fetching models: {str(e)}")
        return {"success": False, "models": []}

# --- Permissions & Rollback API endpoints ---
@app.get("/api/permissions")
def get_permissions():
    project_id = permission_manager._get_project_id()
    project_perms = config_manager.get_project_permissions(project_id)
    session_perms = list(permission_manager.session_permissions)
    return {
        "project": project_perms,
        "session": session_perms
    }

@app.post("/api/permissions/grant")
def grant_permission(req: PermissionGrantRequest):
    permission_manager.grant_permission(req.command, req.scope)
    return {"success": True}

@app.post("/api/permissions/revoke")
def revoke_permission(req: PermissionRevokeRequest):
    if req.scope == "session":
        cmd_pattern = permission_manager._get_command_pattern(req.command)
        if cmd_pattern in permission_manager.session_permissions:
            permission_manager.session_permissions.remove(cmd_pattern)
    elif req.scope == "project":
        permission_manager.revoke_project_permission(req.command)
    return {"success": True}

@app.post("/api/rollback")
def rollback_file_endpoint(req: RollbackRequest):
    from .files import rollback_file
    success = rollback_file(workspace_state.root, req.path, req.timestamp)
    if not success:
        raise HTTPException(status_code=400, detail="No backup available for rollback or rollback failed.")
    return {"success": True}

@app.get("/api/files/backups")
def get_file_backups(path: str):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        import hashlib, glob
        rel_hash = hashlib.md5(path.encode("utf-8")).hexdigest()
        backup_dir = os.path.join(workspace_state.root, ".devpilot", "backups", rel_hash)
        if not os.path.exists(backup_dir):
            return {"backups": []}
        baks = sorted(glob.glob(os.path.join(backup_dir, "*.bak")))
        backups_list = []
        for b in baks:
            filename = os.path.basename(b)
            ts_str = filename.replace(".bak", "")
            try:
                ts = int(ts_str)
                backups_list.append({"timestamp": ts, "filename": filename})
            except ValueError:
                pass
        return {"backups": backups_list[::-1]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config/settings")
def get_settings():
    return {
        "exclude_list": config_manager.get_exclude_list(),
        "auto_backup_enabled": config_manager.get_auto_backup_enabled(),
        "agent_model_name": config_manager.get_agent_model_name()
    }

@app.post("/api/config/settings")
def save_settings(req: SettingsUpdateRequest):
    try:
        config_manager.set_exclude_list(req.exclude_list)
        config_manager.set_auto_backup_enabled(req.auto_backup_enabled)
        config_manager.set_agent_model_name(req.agent_model_name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test-connection")
async def test_connection(profile: ProfileSaveRequest):
    try:
        fmt = profile.api_format
        key = profile.api_key
        url = profile.base_url
        model = profile.model_name
        
        # If API key is masked, retrieve the original saved key from disk
        if "..." in key or "*" in key:
            saved = config_manager.get_profile(profile.id or "")
            if saved:
                key = saved["api_key"]
                
        if fmt == "anthropic":
            from anthropic import AsyncAnthropic
            # Only use custom base url if it's not standard and not empty
            base_url = url if (url and "api.anthropic.com" not in url) else None
            client = AsyncAnthropic(api_key=key, base_url=base_url)
            await client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            from openai import AsyncOpenAI
            base_url = url if url else None
            client = AsyncOpenAI(api_key=key, base_url=base_url)
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        return {"success": True, "message": "Connection succeeded"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- File Explorer REST endpoints ---

@app.get("/api/files")
def get_files(path: str = ""):
    try:
        if not workspace_state.root:
            return []
        return list_workspace_dir(workspace_state.root, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/content")
def get_file_content(path: str):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        content = read_workspace_file(workspace_state.root, path)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/create")
def create_file(req: FileCreateRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        abs_path = safe_path(workspace_state.root, req.path)
        if req.is_dir:
            os.makedirs(abs_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            if not os.path.exists(abs_path):
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write("")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/save")
def save_file(req: FileSaveRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        write_workspace_file(workspace_state.root, req.path, req.content)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/delete")
def delete_file(req: FileDeleteRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        delete_workspace_item(workspace_state.root, req.path)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/rename")
def rename_file(req: FileRenameRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        abs_old = safe_path(workspace_state.root, req.old_path)
        abs_new = safe_path(workspace_state.root, req.new_path)
        
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(abs_new), exist_ok=True)
        shutil.move(abs_old, abs_new)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/search")
def get_codebase_search(query: str):
    try:
        if not workspace_state.root:
            return []
        return search_workspace_codebase(workspace_state.root, query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Git Integration endpoints ---
@app.get("/api/git/status")
async def get_git_status():
    if not workspace_state.root:
        return {"branch": "", "files": []}
    try:
        branch = await run_cmd_async("git rev-parse --abbrev-ref HEAD", workspace_state.root)
        if "fatal:" in branch:
            return {"branch": "Not a Git Repository", "files": []}
        branch = branch.strip()
        status_out = await run_cmd_async("git status --porcelain", workspace_state.root)
        if "fatal:" in status_out:
            return {"branch": "Not a Git Repository", "files": []}
        files = []
        for line in status_out.splitlines():
            if len(line) > 3:
                status = line[:2].strip()
                path = line[3:].strip()
                # strip quotes if any
                path = path.strip('"').strip("'")
                files.append({"path": path, "status": status})
        return {"branch": branch, "files": files}
    except Exception as e:
        return {"branch": "unknown", "files": [], "error": str(e)}

@app.get("/api/git/branches")
async def get_git_branches():
    if not workspace_state.root:
        return {"branches": []}
    try:
        out = await run_cmd_async("git branch -a", workspace_state.root)
        if "fatal:" in out:
            return {"branches": []}
        branches = [line.replace("*", "").strip() for line in out.splitlines() if line.strip()]
        return {"branches": branches}
    except Exception as e:
        return {"branches": [], "error": str(e)}

@app.get("/api/git/history")
async def get_git_history():
    if not workspace_state.root:
        return {"history": []}
    try:
        out = await run_cmd_async('git log -n 15 --pretty=format:"%h - %an, %ar : %s"', workspace_state.root)
        if "fatal:" in out:
            return {"history": []}
        history = [line.strip() for line in out.splitlines() if line.strip()]
        return {"history": history}
    except Exception as e:
        return {"history": [], "error": str(e)}

@app.post("/api/git/action")
async def perform_git_action(req: GitActionRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        if req.action == "stage":
            await run_cmd_async(f"git add {req.path}", workspace_state.root)
        elif req.action == "unstage":
            await run_cmd_async(f"git restore --staged {req.path}", workspace_state.root)
        elif req.action == "commit":
            await run_cmd_async(f'git commit -m "{req.message}"', workspace_state.root)
        elif req.action == "push":
            await run_cmd_async("git push", workspace_state.root)
        elif req.action == "pull":
            await run_cmd_async("git pull", workspace_state.root)
        elif req.action == "checkout":
            await run_cmd_async(f"git checkout {req.branch}", workspace_state.root)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Packages endpoints ---
@app.get("/api/packages/list")
def list_packages():
    if not workspace_state.root:
        return {"manager": "npm", "dependencies": []}
    
    # Check node packages
    pkg_json_path = os.path.join(workspace_state.root, "package.json")
    if os.path.exists(pkg_json_path):
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                deps = []
                # Combine dep + devDep
                for k, v in data.get("dependencies", {}).items():
                    deps.append({"name": k, "version": v, "type": "production"})
                for k, v in data.get("devDependencies", {}).items():
                    deps.append({"name": k, "version": v, "type": "development"})
                return {"manager": "npm", "dependencies": deps}
        except Exception:
            pass

    # Check python packages
    req_txt_path = os.path.join(workspace_state.root, "requirements.txt")
    if os.path.exists(req_txt_path):
        try:
            deps = []
            with open(req_txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split("==")
                        name = parts[0]
                        ver = parts[1] if len(parts) > 1 else "latest"
                        deps.append({"name": name, "version": ver, "type": "pip"})
            return {"manager": "pip", "dependencies": deps}
        except Exception:
            pass
            
    return {"manager": "npm", "dependencies": []}

@app.post("/api/packages/install")
async def install_package(req: PackageInstallRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        # Detect package manager
        pkg_json_path = os.path.join(workspace_state.root, "package.json")
        if os.path.exists(pkg_json_path):
            cmd = f"npm install {req.name}"
        else:
            cmd = f"pip install {req.name}"
        out = await run_cmd_async(cmd, workspace_state.root)
        return {"success": True, "output": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/packages/uninstall")
async def uninstall_package(req: PackageUninstallRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        pkg_json_path = os.path.join(workspace_state.root, "package.json")
        if os.path.exists(pkg_json_path):
            cmd = f"npm uninstall {req.name}"
        else:
            cmd = f"pip uninstall -y {req.name}"
        out = await run_cmd_async(cmd, workspace_state.root)
        return {"success": True, "output": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Debug Process Runner State & Endpoints ---
class DebugProcessState:
    def __init__(self):
        self.process = None
        self.logs = []
        self.log_lock = asyncio.Lock()

    async def add_log(self, text: str):
        async with self.log_lock:
            self.logs.append(text)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]

debug_state = DebugProcessState()

async def read_stream(stream, callback):
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            await callback(line.decode("utf-8", errors="replace").strip())
    except Exception:
        pass

@app.post("/api/debug/start")
async def start_debug_session():
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    if debug_state.process and debug_state.process.returncode is None:
        return {"success": True, "message": "Debugger already running."}

    debug_state.logs = []
    await debug_state.add_log("Starting Debug Session...")

    # Detect start command
    cmd = "npm run dev"
    if not os.path.exists(os.path.join(workspace_state.root, "package.json")):
        if os.path.exists(os.path.join(workspace_state.root, "main.py")):
            cmd = "python main.py"
        elif os.path.exists(os.path.join(workspace_state.root, "run.py")):
            cmd = "python run.py"
        else:
            cmd = "python -m http.server 8000"

    try:
        debug_state.process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace_state.root
        )
        
        asyncio.create_task(read_stream(debug_state.process.stdout, debug_state.add_log))
        asyncio.create_task(read_stream(debug_state.process.stderr, debug_state.add_log))
        
        await debug_state.add_log(f"Spawned debug process: {cmd}")
        return {"success": True, "command": cmd}
    except Exception as e:
        await debug_state.add_log(f"Failed to spawn debug process: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/api/debug/stop")
async def stop_debug_session():
    if debug_state.process and debug_state.process.returncode is None:
        try:
            debug_state.process.terminate()
            await debug_state.process.wait()
            await debug_state.add_log("Debug process terminated.")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "message": "Debugger not running."}

@app.get("/api/debug/status")
def get_debug_status():
    running = debug_state.process is not None and debug_state.process.returncode is None
    return {"running": running}

@app.get("/api/debug/logs")
def get_debug_logs():
    return {"logs": debug_state.logs}

# --- Extensions persistence endpoints ---
EXTENSIONS_FILE_PATH = os.path.expanduser("~/.devpilot/extensions.json")

def get_installed_extensions_list():
    os.makedirs(os.path.dirname(EXTENSIONS_FILE_PATH), exist_ok=True)
    if os.path.exists(EXTENSIONS_FILE_PATH):
        try:
            with open(EXTENSIONS_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # default list
    defaults = [
        {"id": "python", "name": "Python Rich Language", "description": "Syntax highlighting, auto-completions, and debug configs", "version": "v2.1.0", "installed": True},
        {"id": "prettier", "name": "Prettier Code Formatter", "description": "Opinionated code formatter for TS, JS, CSS, and HTML", "version": "v3.0.1", "installed": True},
        {"id": "gitlens", "name": "GitLens Sidebar tool", "description": "Visualize git commit history, lines details, and blame logs", "version": "v11.4.0", "installed": false},
        {"id": "copilot", "name": "DevPilot Autocomplete", "description": "Real-time AI inline code completions suggestions", "version": "v1.0.0", "installed": True},
        {"id": "docker", "name": "Docker integration", "description": "Manage Docker containers, networks, and images", "version": "v1.22.0", "installed": false}
    ]
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(defaults, f)
    return defaults

@app.get("/api/extensions/installed")
def get_installed_extensions():
    return {"extensions": get_installed_extensions_list()}

@app.post("/api/extensions/install")
def install_extension(req: ExtensionActionRequest):
    exts = get_installed_extensions_list()
    matched = False
    for ext in exts:
        if ext["id"] == req.id:
            ext["installed"] = True
            matched = True
            break
    if not matched:
        exts.append({
            "id": req.id,
            "name": req.name or req.id,
            "description": req.description or "",
            "version": req.version or "v1.0.0",
            "installed": True
        })
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f)
    return {"success": True}

@app.post("/api/extensions/uninstall")
def uninstall_extension(req: ExtensionActionRequest):
    exts = get_installed_extensions_list()
    for ext in exts:
        if ext["id"] == req.id:
            ext["installed"] = False
            break
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f)
    return {"success": True}

# --- Testing endpoints ---
@app.get("/api/testing/discover")
def discover_tests():
    if not workspace_state.root:
        return {"tests": []}
    
    test_files = []
    # Glob for files containing 'test'
    for root, dirs, files in os.walk(workspace_state.root):
        if any(d in root for d in {".git", "node_modules", "venv", "__pycache__", ".devpilot"}):
            continue
        for f in files:
            if "test" in f.lower() and os.path.splitext(f)[1].lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                rel_path = os.path.relpath(os.path.join(root, f), workspace_state.root).replace("\\", "/")
                test_files.append(rel_path)
    return {"tests": test_files}

@app.post("/api/testing/run")
async def run_tests(req: TestRunRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        # Build logical test command
        if req.file:
            if req.file.endswith(".py"):
                cmd = f"python -m unittest {req.file}"
            else:
                cmd = f"npm test {req.file}"
        else:
            if os.path.exists(os.path.join(workspace_state.root, "package.json")):
                cmd = "npm test"
            else:
                cmd = "pytest"
        out = await run_cmd_async(cmd, workspace_state.root)
        passed = "FAIL" not in out and "ERROR" not in out and "failed" not in out.lower()
        return {"success": True, "passed": passed, "output": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_cmd_async(cmd: str, cwd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd
    )
    stdout, stderr = await proc.communicate()
    return (stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")).strip()

CHAT_HISTORY_FILE_PATH = os.path.expanduser("~/.devpilot/chat_history.json")

@app.get("/api/chat/history")
def get_chat_history():
    os.makedirs(os.path.dirname(CHAT_HISTORY_FILE_PATH), exist_ok=True)
    if os.path.exists(CHAT_HISTORY_FILE_PATH):
        try:
            with open(CHAT_HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
                return {"messages": json.load(f)}
        except Exception:
            pass
    return {"messages": []}

@app.post("/api/chat/history")
def save_chat_history(req: ChatHistoryRequest):
    os.makedirs(os.path.dirname(CHAT_HISTORY_FILE_PATH), exist_ok=True)
    try:
        with open(CHAT_HISTORY_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(req.messages, f, indent=2)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/workspace/stats")
async def get_workspace_stats():
    if not workspace_state.root:
        return {"total_files": 0, "total_lines": 0, "languages": {}, "git_commits": 0}
    try:
        total_files = 0
        total_lines = 0
        languages = {}
        
        # Scan files
        for root, dirs, files in os.walk(workspace_state.root):
            if any(d in root for d in {".git", "node_modules", "venv", "__pycache__", ".devpilot", "dist", "build"}):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}:
                    continue
                abs_path = os.path.join(root, f)
                total_files += 1
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                        lines = file_obj.readlines()
                        total_lines += len(lines)
                except Exception:
                    pass
                
                # Group by extension/language name
                lang_name = "Unknown"
                if ext == ".py": lang_name = "Python"
                elif ext in {".ts", ".tsx"}: lang_name = "TypeScript"
                elif ext in {".js", ".jsx"}: lang_name = "JavaScript"
                elif ext == ".json": lang_name = "JSON"
                elif ext == ".css": lang_name = "CSS"
                elif ext == ".html": lang_name = "HTML"
                elif ext == ".md": lang_name = "Markdown"
                
                languages[lang_name] = languages.get(lang_name, 0) + 1

        # Git commit count
        git_commits = 0
        try:
            commits_out = await run_cmd_async("git rev-list --count HEAD", workspace_state.root)
            if "fatal:" not in commits_out:
                git_commits = int(commits_out.strip())
        except Exception:
            pass

        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "languages": languages,
            "git_commits": git_commits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- WebSocket Endpoints ---

@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()
    
    # Callback to send terminal output to websocket
    async def send_to_client(data: str):
        try:
            await websocket.send_text(data)
        except Exception:
            pass
            
    term_manager = TerminalManager(workspace_state.root, send_to_client)
    await term_manager.start()
    
    try:
        while True:
            # Wait for data sent from frontend (xterm keypresses/commands)
            data = await websocket.receive_text()
            await term_manager.write(data)
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected")
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {str(e)}")
    finally:
        await term_manager.stop()

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    
    # Get active connection profile from manager
    active_profile = config_manager.get_active_profile()
    
    async def send_to_client(data: dict):
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass
            
    session = AgentSession(workspace_state.root, active_profile, send_to_client, permission_manager)
    
    try:
        while True:
            # Wait for user requests
            raw_msg = await websocket.receive_text()
            msg = json.loads(raw_msg)
            msg_type = msg.get("type")
            
            if msg_type == "user_message":
                text = msg.get("text", "")
                mode = msg.get("mode", "Ask")
                auto_apply = msg.get("auto_apply", False)
                # Run the agent execution loop in the background task
                # Refresh session root in case it changed mid-socket session
                session.workspace_root = workspace_state.root
                if session.active_task and not session.active_task.done():
                    session.active_task.cancel()
                session.active_task = asyncio.create_task(session.handle_user_message(text, mode, auto_apply))
                
            elif msg_type == "confirm_response":
                # User clicked Accept or Reject
                tool_call_id = msg.get("tool_call_id")
                approved = msg.get("approved", False)
                scope = msg.get("scope", "once")
                edited_command = msg.get("command", None)
                hunk_decisions = msg.get("hunk_decisions", None)
                session.resolve_confirmation(tool_call_id, approved, scope, edited_command, hunk_decisions)
                
            elif msg_type == "change_profile":
                # Hot-reload active profile in active session if changed
                new_profile = config_manager.get_active_profile()
                session.profile = new_profile
                
            elif msg_type == "cancel_generation":
                if session.active_task and not session.active_task.done():
                    session.active_task.cancel()
                    logger.info("Agent session task cancelled by user request.")
                
    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {str(e)}")

# --- Serve Compiled Static Frontend ---
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

