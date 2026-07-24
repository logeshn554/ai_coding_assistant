import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..state import workspace_state, logger
from ..project_detector import detect_project_metadata
from ..processes import global_process_manager

router = APIRouter()

class UpdateProjectMetadataRequest(BaseModel):
    installCommand: Optional[str] = None
    runCommand: Optional[str] = None
    buildCommand: Optional[str] = None
    testCommand: Optional[str] = None

@router.get("/api/project/metadata")
async def get_project_metadata():
    """
    Returns current project metadata and stored execution commands.
    Reads from .devpilot/project.json or runs fresh detection if missing.
    """
    root = (workspace_state.root or "").strip()
    if not root or not os.path.exists(root):
        return {
            "projectId": "default",
            "name": "DevPilot Workspace",
            "framework": "Plain Workspace",
            "language": "General",
            "packageManager": "npm",
            "installCommand": "",
            "runCommand": "",
            "buildCommand": "",
            "testCommand": "",
            "workspace": root
        }

    meta_path = os.path.join(root, ".devpilot", "project.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"Error reading project.json: {e}")

    # Fall back to fresh detection
    return detect_project_metadata(root)

@router.post("/api/project/analyze")
async def analyze_project():
    """
    Triggers fresh project stack analysis and updates stored metadata.
    """
    root = (workspace_state.root or "").strip()
    metadata = detect_project_metadata(root)
    return metadata

@router.post("/api/project/metadata")
async def update_project_metadata(req: UpdateProjectMetadataRequest):
    """
    Updates stored project execution commands in .devpilot/project.json.
    """
    root = (workspace_state.root or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="No active workspace root")

    meta = detect_project_metadata(root)
    if req.installCommand is not None:
        meta["installCommand"] = req.installCommand
    if req.runCommand is not None:
        meta["runCommand"] = req.runCommand
    if req.buildCommand is not None:
        meta["buildCommand"] = req.buildCommand
    if req.testCommand is not None:
        meta["testCommand"] = req.testCommand

    try:
        devpilot_dir = os.path.join(root, ".devpilot")
        os.makedirs(devpilot_dir, exist_ok=True)
        meta_file = os.path.join(devpilot_dir, "project.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return meta

@router.post("/api/project/run")
async def run_project():
    """
    Launches the stored project runCommand in the process manager.
    """
    root = (workspace_state.root or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="No active workspace root")

    meta = detect_project_metadata(root)
    run_cmd = meta.get("runCommand", "").strip()
    if not run_cmd:
        raise HTTPException(status_code=400, detail="No run command specified for this project.")

    try:
        proc = await global_process_manager.start_process(run_cmd, root, name=meta.get("framework", "Application"))
        return {
            "success": True,
            "command": run_cmd,
            "process_id": proc.id,
            "pid": proc.pid
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch project: {str(e)}")
