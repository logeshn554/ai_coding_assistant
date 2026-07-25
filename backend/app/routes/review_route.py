import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import workspace_state
from ..code_reviewer import review_workspace

router = APIRouter()


class FixFindingRequest(BaseModel):
    finding_id: str
    file_path: str


@router.post("/api/review/scan")
async def scan_workspace_review():
    """
    Performs full static audit scan of the workspace.
    """
    root = (workspace_state.root or "").strip()
    if not root or not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="No active workspace root")

    report = review_workspace(root)
    return report


@router.post("/api/review/fix")
async def fix_finding(req: FixFindingRequest):
    """
    Applies auto-fix to a specific review finding.
    """
    root = (workspace_state.root or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="No active workspace root")

    abs_path = os.path.join(root, req.file_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"File {req.file_path} not found")

    try:
        content = open(abs_path, "r", encoding="utf-8", errors="ignore").read()
        # Auto-remove console.log statements
        fixed_content = content
        lines = fixed_content.splitlines()
        new_lines = [l for l in lines if "console.log(" not in l]
        fixed_content = "\n".join(new_lines)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(fixed_content)

        return {"success": True, "file_path": req.file_path, "message": "Auto-fix applied successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
