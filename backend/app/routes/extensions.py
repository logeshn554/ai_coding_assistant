import httpx
import json
import os
import tempfile
import urllib.parse
import zipfile
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ..extension_host import extension_host

router = APIRouter()

EXTENSIONS_FILE_PATH = os.path.expanduser("~/.devpilot/extensions.json")
CUSTOM_EXTENSIONS_DIR = os.path.expanduser("~/.devpilot/custom_extensions")


class ExtensionActionRequest(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    version: str | None = None
    category: str | None = None
    publisher: str | None = None
    download_url: str | None = None


class ToggleStateRequest(BaseModel):
    id: str
    enabled: bool


class ExecuteCommandRequest(BaseModel):
    command_id: str
    payload: dict[str, Any] | None = None


def get_installed_extensions_list() -> list[dict[str, Any]]:
    os.makedirs(os.path.dirname(EXTENSIONS_FILE_PATH), exist_ok=True)
    os.makedirs(CUSTOM_EXTENSIONS_DIR, exist_ok=True)
    if os.path.exists(EXTENSIONS_FILE_PATH):
        try:
            with open(EXTENSIONS_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Clean initial registry
    initial = [
        {"id": "ms-python.python", "name": "Python", "description": "IntelliSense, linting, debugging, code formatting, and refactoring", "version": "2024.2.0", "category": "Programming Languages", "installed": True, "enabled": True, "publisher": "ms-python"},
        {"id": "esbenp.prettier-vscode", "name": "Prettier - Code formatter", "description": "Code formatter using prettier for JS, TS, HTML, CSS", "version": "10.4.0", "category": "Formatters", "installed": True, "enabled": True, "publisher": "esbenp"},
        {"id": "dbaeumer.vscode-eslint", "name": "ESLint", "description": "Integrates ESLint into DevPilot editor", "version": "2.4.4", "category": "Linters", "installed": True, "enabled": True, "publisher": "dbaeumer"},
        {"id": "devpilot.core-ai", "name": "DevPilot AI Agent Assistant", "description": "Autonomous AI reasoning, inline multi-file editing & LSP integration", "version": "1.0.0", "category": "AI", "installed": True, "enabled": True, "publisher": "devpilot"},
    ]
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(initial, f, indent=2)
    return initial


def save_installed_extensions_list(exts: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(EXTENSIONS_FILE_PATH), exist_ok=True)
    with open(EXTENSIONS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(exts, f, indent=2)
    extension_host.reload_extensions()


@router.get("/api/extensions/installed")
def get_installed_extensions():
    return {"extensions": get_installed_extensions_list()}


@router.get("/api/extensions/active")
def get_active_extensions():
    """
    Returns active extension runtime state & all loaded capabilities
    (commands, snippets, AI tools, settings, execution logs).
    """
    return extension_host.get_summary()


@router.post("/api/extensions/execute")
async def execute_extension_command(req: ExecuteCommandRequest):
    """
    Executes a dynamic extension command or action.
    """
    res = await extension_host.execute_command(req.command_id, req.payload)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Execution failed"))
    return res


@router.get("/api/extensions/active-tools")
def get_extension_active_tools():
    """
    Returns active AI tools contributed by extensions.
    """
    return {"tools": list(extension_host.registered_ai_tools.values())}


@router.get("/api/extensions/search")
async def search_marketplace_extensions(query: str = Query("", description="Search term for Open VSX marketplace"), size: int = 25):
    """
    Search real VS Code extensions dynamically from the Open VSX Registry.
    """
    installed_map = {e["id"]: e for e in get_installed_extensions_list()}

    if not query.strip():
        search_term = "python"
    else:
        search_term = query.strip()

    encoded_query = urllib.parse.quote(search_term)
    url = f"https://open-vsx.org/api/-/search?query={encoded_query}&size={size}&sortBy=downloadCount&sortOrder=desc"

    results = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "DevPilot-AI-Editor/1.0", "Accept": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_exts = data.get("extensions", [])
                for ext in raw_exts:
                    namespace = ext.get("namespace", "")
                    name = ext.get("name", "")
                    ext_id = f"{namespace}.{name}" if namespace else name
                    display_name = ext.get("displayName") or name
                    description = ext.get("description") or ""
                    version = ext.get("version") or "1.0.0"

                    files = ext.get("files", {})
                    download_url = files.get("download") or f"https://open-vsx.org/api/{namespace}/{name}/{version}/file/{namespace}.{name}-{version}.vsix"
                    icon_url = files.get("icon")

                    is_installed = ext_id in installed_map and installed_map[ext_id].get("installed", False)
                    is_enabled = installed_map.get(ext_id, {}).get("enabled", True) if is_installed else False

                    results.append({
                        "id": ext_id,
                        "name": display_name,
                        "description": description,
                        "version": version,
                        "category": ext.get("categories", ["General"])[0] if ext.get("categories") else "General",
                        "publisher": namespace or ext.get("publisher", "community"),
                        "download_url": download_url,
                        "icon_url": icon_url,
                        "downloads": ext.get("downloadCount", 0),
                        "installed": is_installed,
                        "enabled": is_enabled
                    })
    except Exception:
        for ext in get_installed_extensions_list():
            if query.lower() in ext.get("name", "").lower() or query.lower() in ext.get("description", "").lower():
                results.append(ext)

    return {"extensions": results, "total": len(results)}


@router.post("/api/extensions/install")
async def install_extension(req: ExtensionActionRequest):
    """
    Installs an extension. Downloads and unpacks package into custom_extensions,
    then automatically loads and activates it in the IDE runtime.
    """
    exts = get_installed_extensions_list()
    dest_dir = os.path.join(CUSTOM_EXTENSIONS_DIR, req.id.replace("/", "_").replace("\\", "_"))

    download_url = req.download_url
    if not download_url and "." in req.id:
        parts = req.id.split(".", 1)
        ver = req.version or "latest"
        download_url = f"https://open-vsx.org/api/{parts[0]}/{parts[1]}/{ver}/file/{parts[0]}.{parts[1]}-{ver}.vsix"

    if download_url:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                vsix_file = os.path.join(tmp_dir, "pkg.vsix")
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    resp = await client.get(
                        download_url,
                        headers={"User-Agent": "DevPilot-AI-Editor/1.0"}
                    )
                    with open(vsix_file, "wb") as out_f:
                        out_f.write(resp.content)

                os.makedirs(dest_dir, exist_ok=True)
                with zipfile.ZipFile(vsix_file, "r") as zf:
                    zf.extractall(dest_dir)
        except Exception:
            os.makedirs(dest_dir, exist_ok=True)

    matched = False
    for ext in exts:
        if ext["id"] == req.id:
            ext["installed"] = True
            ext["enabled"] = True
            if req.version:
                ext["version"] = req.version
            if req.description:
                ext["description"] = req.description
            matched = True
            break
    if not matched:
        exts.append({
            "id": req.id,
            "name": req.name or req.id,
            "description": req.description or "Installed extension",
            "version": req.version or "1.0.0",
            "category": req.category or "General",
            "publisher": req.publisher or (req.id.split(".")[0] if "." in req.id else "community"),
            "installed": True,
            "enabled": True,
            "install_path": dest_dir
        })

    save_installed_extensions_list(exts)
    return {"success": True, "id": req.id}


@router.post("/api/extensions/toggle-enable")
def toggle_extension_enable(req: ToggleStateRequest):
    exts = get_installed_extensions_list()
    for ext in exts:
        if ext["id"] == req.id:
            ext["enabled"] = req.enabled
            break
    save_installed_extensions_list(exts)
    return {"success": True}


@router.post("/api/extensions/uninstall")
def uninstall_extension(req: ExtensionActionRequest):
    exts = get_installed_extensions_list()
    for ext in exts:
        if ext["id"] == req.id:
            ext["installed"] = False
            ext["enabled"] = False
            break
    save_installed_extensions_list(exts)
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
            dest_dir = os.path.join(CUSTOM_EXTENSIONS_DIR, ext_id.replace("/", "_"))
            os.makedirs(dest_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_dir)

            ext_item = {
                "id": ext_id,
                "name": manifest_data.get("displayName") or manifest_data.get("name", "Custom Extension"),
                "description": manifest_data.get("description", "VSIX Extension"),
                "version": manifest_data.get("version", "1.0.0"),
                "category": "VSIX Package",
                "installed": True,
                "enabled": True,
                "publisher": manifest_data.get("publisher", "local"),
                "install_path": dest_dir
            }

            exts = get_installed_extensions_list()
            exts = [e for e in exts if e["id"] != ext_id]
            exts.append(ext_item)
            save_installed_extensions_list(exts)

            return {"success": True, "extension": ext_item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse VSIX package: {e!s}")
