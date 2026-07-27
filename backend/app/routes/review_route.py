import asyncio
import os
import re
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
    Performs full static audit scan of the workspace (non-blocking).
    """
    root = (workspace_state.root or "").strip()
    if not root or not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="No active workspace root")

    report = await asyncio.to_thread(review_workspace, root)
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
        fixed_content = content

        # 1. Console log leftovers
        if "console" in req.finding_id or "Maintainability" in req.finding_id or "console.log" in content:
            fixed_content = re.sub(r'^\s*console\.log\s*\(.*?\);?\s*$', '', fixed_content, flags=re.MULTILINE)
            fixed_content = re.sub(r'console\.log\s*\([^;]*\);?', '', fixed_content)

        # 2. TypeScript loose `: any` annotations
        if "any" in req.finding_id or "TypeScript" in req.finding_id or "Type" in req.finding_id:
            fixed_content = re.sub(r':\s*any\b', ': unknown', fixed_content)

        # 3. Unhandled floating promises without await
        if "promise" in req.finding_id.lower() or "async" in req.finding_id.lower():
            fixed_content = re.sub(r'^\s*(fetch\(.*?\));', r'await \1;', fixed_content, flags=re.MULTILINE)

        if fixed_content != content:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            return {"success": True, "file_path": req.file_path, "message": "Auto-fix applied successfully."}
        else:
            return {"success": True, "file_path": req.file_path, "message": "No matching patterns to fix."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


