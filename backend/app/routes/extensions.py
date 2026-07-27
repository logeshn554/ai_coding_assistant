import os
import json
import zipfile
import tempfile
from typing import Optional, List
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

router = APIRouter()

EXTENSIONS_FILE_PATH = os.path.expanduser("~/.devpilot/extensions.json")
CUSTOM_EXTENSIONS_DIR = os.path.expanduser("~/.devpilot/custom_extensions")

class ExtensionActionRequest(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None

class ToggleStateRequest(BaseModel):
    id: str
    enabled: bool

def get_installed_extensions_list():
    os.makedirs(os.path.dirname(EXTENSIONS_FILE_PATH), exist_ok=True)
    os.makedirs(CUSTOM_EXTENSIONS_DIR, exist_ok=True)
    if os.path.exists(EXTENSIONS_FILE_PATH):
        try:
            with open(EXTENSIONS_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    # Defaults
    defaults = [
        {"id": "python", "name": "Python Language Server", "description": "Syntax highlighting, auto-completions, and debug configs", "version": "v2.4.0", "category": "Languages", "installed": True, "enabled": True, "publisher": "ms-python"},
        {"id": "prettier", "name": "Prettier Code Formatter", "description": "Opinionated code formatter for TS, JS, CSS, and HTML", "version": "v3.2.0", "category": "Formatters", "installed": True, "enabled": True, "publisher": "esbenp"},
        {"id": "eslint", "name": "ESLint Linter", "description": "Integrates ESLint JavaScript into the editor", "version": "v2.4.2", "category": "Linters", "installed": True, "enabled": True, "publisher": "dbaeumer"},
        {"id": "gitlens", "name": "GitLens Extension", "description": "Visualize git commit history, lines details, and blame logs", "version": "v12.0.0", "category": "Git", "installed": False, "enabled": False, "publisher": "eamodio"},
        {"id": "copilot", "name": "DevPilot AI Agent", "description": "Real-time AI inline code completions suggestions & Chat OS", "version": "v1.5.0", "category": "AI", "installed": True, "enabled": True, "publisher": "devpilot"},

        {"id": "docker", "name": "Docker Container Tool", "description": "Manage Docker containers, networks, and images", "version": "v1.23.0", "category": "DevOps", "installed": False, "enabled": False, "publisher": "ms-azuretools"},
        {"id": "dracula", "name": "Dracula Official Theme", "description": "Dark theme for VS Code with vibrant accent colors", "version": "v2.24.0", "category": "Themes", "installed": False, "enabled": False, "publisher": "dracula-theme"}
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
            ext["enabled"] = True
            matched = True
            break
    if not matched:
        exts.append({
            "id": req.id,
            "name": req.name or req.id,
            "description": req.description or "",
            "version": req.version or "v1.0.0",
            "category": req.category or "General",
            "installed": True,
            "enabled": True,
            "publisher": "custom"
        })
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f)
    return {"success": True}

@router.post("/api/extensions/toggle-enable")
def toggle_extension_enable(req: ToggleStateRequest):
    exts = get_installed_extensions_list()
    for ext in exts:
        if ext["id"] == req.id:
            ext["enabled"] = req.enabled
            break
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f)
    return {"success": True}

@router.post("/api/extensions/uninstall")
def uninstall_extension(req: ExtensionActionRequest):
    exts = get_installed_extensions_list()
    for ext in exts:
        if ext["id"] == req.id:
            ext["installed"] = False
            ext["enabled"] = False
            break
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f)
    return {"success": True}

@router.post("/api/extensions/load-vsix")
async def load_vsix_package(file: UploadFile = File(...)):
    """
    Parses a local .vsix / .zip extension manifest package and registers it.
    """
    filename = file.filename.lower()
    if not (filename.endswith(".vsix") or filename.endswith(".zip")):
        raise HTTPException(status_code=400, detail="Only .vsix or .zip extension packages are supported.")

    try:
        contents = await file.read()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = os.path.join(tmp_dir, "ext.zip")
            with open(zip_path, "wb") as f:
                f.write(contents)

            manifest_data = {}
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Look for extension/package.json or package.json
                for item in zf.namelist():
                    if item.endswith("package.json"):
                        manifest_raw = zf.read(item)
                        manifest_data = json.loads(manifest_raw.decode("utf-8"))
                        break

            if not manifest_data:
                manifest_data = {
                    "name": filename.replace(".vsix", "").replace(".zip", ""),
                    "publisher": "local-vsix",
                    "description": "Installed via local VSIX package loader",
                    "version": "1.0.0"
                }

            ext_id = f"{manifest_data.get('publisher', 'user')}.{manifest_data.get('name', 'custom-ext')}"
            ext_item = {
                "id": ext_id,
                "name": manifest_data.get("displayName") or manifest_data.get("name", "Custom Extension"),
                "description": manifest_data.get("description", "VSIX Extension"),
                "version": manifest_data.get("version", "v1.0.0"),
                "category": "VSIX Package",
                "installed": True,
                "enabled": True,
                "publisher": manifest_data.get("publisher", "local")
            }

            exts = get_installed_extensions_list()
            exts = [e for e in exts if e["id"] != ext_id]
            exts.append(ext_item)

            with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(exts, f)

            return {"success": True, "extension": ext_item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse VSIX package: {str(e)}")

