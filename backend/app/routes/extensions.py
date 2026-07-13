import os
import json
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

EXTENSIONS_FILE_PATH = os.path.expanduser("~/.devpilot/extensions.json")

class ExtensionActionRequest(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None

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
        {"id": "gitlens", "name": "GitLens Sidebar tool", "description": "Visualize git commit history, lines details, and blame logs", "version": "v11.4.0", "installed": False},
        {"id": "copilot", "name": "DevPilot Autocomplete", "description": "Real-time AI inline code completions suggestions", "version": "v1.0.0", "installed": True},
        {"id": "docker", "name": "Docker integration", "description": "Manage Docker containers, networks, and images", "version": "v1.22.0", "installed": False}
    ]
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(defaults, f)
    return defaults

@router.get("/api/extensions/installed")
def get_installed_extensions():
    return {"extensions": get_installed_extensions_list()}

@router.post("/api/extensions/install")
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

@router.post("/api/extensions/uninstall")
def uninstall_extension(req: ExtensionActionRequest):
    exts = get_installed_extensions_list()
    for ext in exts:
        if ext["id"] == req.id:
            ext["installed"] = False
            break
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f)
    return {"success": True}
