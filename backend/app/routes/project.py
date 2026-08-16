import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..processes import global_process_manager
from ..project_detector import detect_project_metadata, detect_project_metadata_async
from ..state import workspace_state

router = APIRouter()


class UpdateProjectMetadataRequest(BaseModel):
    installCommand: str | None = None
    runCommand: str | None = None
    buildCommand: str | None = None
    testCommand: str | None = None


@router.get("/api/project/metadata")
async def get_project_metadata():
    """
    Returns the last AI-analysed project metadata (from .devpilot/project.json).
    If no cached result exists the client should call POST /api/project/analyze.
    """
    root = (workspace_state.root or "").strip()
    return detect_project_metadata(root)


@router.post("/api/project/analyze")
async def analyze_project():
    """
    Triggers a fresh AI analysis of the workspace and returns live results.
    This is the authoritative endpoint — it always calls the LLM.
    """
    root = (workspace_state.root or "").strip()
    if not root or not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="No valid workspace root is set.")
    metadata = await detect_project_metadata_async(root)
    return metadata


@router.post("/api/project/metadata")
async def update_project_metadata(req: UpdateProjectMetadataRequest):
    """
    Manually overrides specific execution commands in .devpilot/project.json.
    Useful for users who want to pin a custom run command.
    """
    import json
    from pathlib import Path

    root = (workspace_state.root or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="No active workspace root")

    # Start from cached metadata (don't re-run LLM just for an override)
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
        devpilot_dir = Path(root) / ".devpilot"
        devpilot_dir.mkdir(exist_ok=True)
        (devpilot_dir / "project.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return meta


@router.post("/api/project/run")
async def run_project():
    """
    Launches the AI-detected runCommand in the process manager.
    """
    root = (workspace_state.root or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="No active workspace root")

    # Use cached metadata — don't re-run LLM on every run click
    meta = detect_project_metadata(root)
    run_cmd = (meta.get("runCommand") or "").strip()

    if not run_cmd:
        raise HTTPException(
            status_code=400,
            detail="No run command found. Click ↻ in the Context panel to analyse the project first."
        )

    try:
        proc = await global_process_manager.start_process(
            run_cmd, root, name=meta.get("framework", "Application")
        )
        return {
            "success": True,
            "command": run_cmd,
            "process_id": proc.id,
            "pid": proc.pid,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch project: {e!s}")
