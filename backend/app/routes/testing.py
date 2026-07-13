import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import workspace_state
from ..utils import run_cmd_async

router = APIRouter()

class TestRunRequest(BaseModel):
    file: Optional[str] = None

@router.get("/api/testing/discover")
def discover_tests():
    if not workspace_state.root:
        return {"tests": []}
    
    test_files = []
    for root, dirs, files in os.walk(workspace_state.root):
        if any(d in root for d in {".git", "node_modules", "venv", "__pycache__", ".devpilot"}):
            continue
        for f in files:
            if "test" in f.lower() and os.path.splitext(f)[1].lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                rel_path = os.path.relpath(os.path.join(root, f), workspace_state.root).replace("\\", "/")
                test_files.append(rel_path)
    return {"tests": test_files}

@router.post("/api/testing/run")
async def run_tests(req: TestRunRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        if req.file:
            if req.file.endswith(".py"):
                cmd = f"python -m unittest {req.file}"
            else:
                cmd = f"npm test {req.file}"
        else:
            if os.path.exists(os.path.join(workspace_state.root, "package.json")):
                cmd = "npm test"
            else:
                cmd = "pytest"
        out = await run_cmd_async(cmd, workspace_state.root)
        passed = "FAIL" not in out and "ERROR" not in out and "failed" not in out.lower()
        return {"success": True, "passed": passed, "output": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
