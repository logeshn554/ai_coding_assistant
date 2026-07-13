import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import workspace_state
from ..utils import run_cmd_async

router = APIRouter()

class PackageInstallRequest(BaseModel):
    name: str

class PackageUninstallRequest(BaseModel):
    name: str

@router.get("/api/packages/list")
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

@router.post("/api/packages/install")
async def install_package(req: PackageInstallRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        pkg_json_path = os.path.join(workspace_state.root, "package.json")
        if os.path.exists(pkg_json_path):
            cmd = f"npm install {req.name}"
        else:
            cmd = f"pip install {req.name}"
        out = await run_cmd_async(cmd, workspace_state.root)
        return {"success": True, "output": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/packages/uninstall")
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
