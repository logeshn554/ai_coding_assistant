import asyncio
import json
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..state import workspace_state
from ..utils import run_cmd_async

router = APIRouter()

# S4: Strict package name allow-list pattern.
# Allows standard npm scoped packages (@scope/name), Python packages, and
# version specifiers (name==1.2.3, name>=2.0), but blocks URLs, paths, and
# any shell-special characters.
_PACKAGE_NAME_RE = re.compile(r'^[a-zA-Z0-9@/_\-\.]{1,200}$')

def _validate_package_name(name: str) -> None:
    """Raise HTTPException 400 if the package name is unsafe."""
    if not name or not _PACKAGE_NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid package name: '{name}'. Only alphanumeric characters, @, /, _, -, . are allowed."
        )
    # Reject URLs, git+, paths, absolute paths
    name_lower = name.lower()
    if (
        "://" in name_lower or
        "git+" in name_lower or
        "http" in name_lower or
        "../" in name_lower or
        "..\\" in name_lower or
        name.startswith("/") or
        name.startswith("\\") or
        ":" in name
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Blocked package name: '{name}'. URLs, paths, and absolute paths are not allowed."
        )

class PackageInstallRequest(BaseModel):
    name: str

class PackageUninstallRequest(BaseModel):
    name: str

def _list_packages_sync(workspace_root: str) -> dict:
    # Check node packages
    pkg_json_path = os.path.join(workspace_root, "package.json")
    if os.path.exists(pkg_json_path):
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                deps = []
                for k, v in data.get("dependencies", {}).items():
                    deps.append({"name": k, "version": v, "type": "production"})
                for k, v in data.get("devDependencies", {}).items():
                    deps.append({"name": k, "version": v, "type": "development"})
                return {"manager": "npm", "dependencies": deps}
        except Exception:
            pass

    # Check python packages
    req_txt_path = os.path.join(workspace_root, "requirements.txt")
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

@router.get("/api/packages/list")
async def list_packages():
    if not workspace_state.root:
        return {"manager": "npm", "dependencies": []}
    
    # Run blocking file reads in background thread
    return await asyncio.to_thread(_list_packages_sync, workspace_state.root)

@router.post("/api/packages/install")
async def install_package(req: PackageInstallRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    # S4: Validate package name before passing to npm/pip
    _validate_package_name(req.name)
    try:
        pkg_json_path = os.path.join(workspace_state.root, "package.json")
        pkg_json_exists = await asyncio.to_thread(os.path.exists, pkg_json_path)
        if pkg_json_exists:
            cmd = ["npm", "install", req.name]
        else:
            cmd = ["pip", "install", req.name]
        out = await run_cmd_async(cmd, workspace_state.root)
        return {"success": True, "output": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/packages/uninstall")
async def uninstall_package(req: PackageUninstallRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    # S4: Validate package name before passing to npm/pip
    _validate_package_name(req.name)
    try:
        pkg_json_path = os.path.join(workspace_state.root, "package.json")
        pkg_json_exists = await asyncio.to_thread(os.path.exists, pkg_json_path)
        if pkg_json_exists:
            cmd = ["npm", "uninstall", req.name]
        else:
            cmd = ["pip", "uninstall", "-y", req.name]
        out = await run_cmd_async(cmd, workspace_state.root)
        return {"success": True, "output": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
