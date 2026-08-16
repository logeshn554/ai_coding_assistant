"""Artifacts and Slash Commands API routes for Antigravity AI IDE."""
import os

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

class ArtifactItem(BaseModel):
    id: str
    title: str
    filename: str
    path: str
    content: str
    type: str  # implementation_plan, walkthrough, general
    request_feedback: bool
    summary: str
    updated_at: float

class FeedbackRequest(BaseModel):
    artifact_id: str
    action: str  # approve, request_changes
    comments: str | None = None

@router.get("", response_model=list[ArtifactItem])
async def list_artifacts(workspace_root: str | None = Query(None)):
    """List active artifacts in the workspace or session."""
    artifacts: list[ArtifactItem] = []
    
    # Check workspace root or brain dir for artifacts
    target_dirs = []
    if workspace_root and os.path.exists(workspace_root):
        target_dirs.append(workspace_root)
    
    # Check default brain/artifact locations
    home_dir = os.path.expanduser("~")
    gemini_brain = os.path.join(home_dir, ".gemini", "antigravity-ide", "brain")
    if os.path.exists(gemini_brain):
        for root, _, files in os.walk(gemini_brain):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    target_dirs.append(os.path.dirname(full_path))

    seen_paths = set()
    for d in target_dirs:
        for fname in ["implementation_plan.md", "walkthrough.md"]:
            fpath = os.path.join(d, fname)
            if os.path.exists(fpath) and fpath not in seen_paths:
                seen_paths.add(fpath)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    
                    art_type = "implementation_plan" if "implementation_plan" in fname else "walkthrough"
                    title = "Implementation Plan" if art_type == "implementation_plan" else "Walkthrough"
                    if content.startswith("# "):
                        title = content.splitlines()[0].replace("# ", "").strip()
                        
                    artifacts.append(
                        ArtifactItem(
                            id=fname.replace(".md", ""),
                            title=title,
                            filename=fname,
                            path=fpath,
                            content=content,
                            type=art_type,
                            request_feedback=(art_type == "implementation_plan"),
                            summary=f"Artifact {fname} in workspace",
                            updated_at=os.path.getmtime(fpath)
                        )
                    )
                except Exception:
                    pass

    return artifacts

@router.post("/feedback")
async def submit_artifact_feedback(req: FeedbackRequest):
    """Process user approval or feedback for an artifact."""
    return {
        "status": "success",
        "action": req.action,
        "artifact_id": req.artifact_id,
        "message": f"Artifact {req.artifact_id} feedback received: {req.action}"
    }
