import os
import shutil
import hashlib
import glob
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import workspace_state, logger
from ..files import (
    list_workspace_dir,
    read_workspace_file,
    write_workspace_file,
    delete_workspace_item,
    safe_path,
    search_workspace_codebase,
    rollback_file
)

router = APIRouter()

class FileCreateRequest(BaseModel):
    path: str
    is_dir: bool

class FileSaveRequest(BaseModel):
    path: str
    content: str

class FileDeleteRequest(BaseModel):
    path: str

class FileRenameRequest(BaseModel):
    old_path: str
    new_path: str

class RollbackRequest(BaseModel):
    path: str
    timestamp: Optional[int] = None

@router.get("/api/files")
def get_files(path: str = ""):
    try:
        if not workspace_state.root:
            return []
        return list_workspace_dir(workspace_state.root, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/files/content")
def get_file_content(path: str):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        content = read_workspace_file(workspace_state.root, path)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/create")
def create_file(req: FileCreateRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        abs_path = safe_path(workspace_state.root, req.path)
        if req.is_dir:
            os.makedirs(abs_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            if not os.path.exists(abs_path):
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write("")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/save")
def save_file(req: FileSaveRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        write_workspace_file(workspace_state.root, req.path, req.content)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/delete")
def delete_file(req: FileDeleteRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        delete_workspace_item(workspace_state.root, req.path)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/rename")
def rename_file(req: FileRenameRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        abs_old = safe_path(workspace_state.root, req.old_path)
        abs_new = safe_path(workspace_state.root, req.new_path)
        os.makedirs(os.path.dirname(abs_new), exist_ok=True)
        shutil.move(abs_old, abs_new)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/files/search")
def get_codebase_search(query: str):
    try:
        if not workspace_state.root:
            return []
        return search_workspace_codebase(workspace_state.root, query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/rollback")
def rollback_file_endpoint(req: RollbackRequest):
    success = rollback_file(workspace_state.root, req.path, req.timestamp)
    if not success:
        raise HTTPException(status_code=400, detail="No backup available for rollback or rollback failed.")
    return {"success": True}

@router.get("/api/files/backups")
def get_file_backups(path: str):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        rel_hash = hashlib.md5(path.encode("utf-8")).hexdigest()
        backup_dir = os.path.join(workspace_state.root, ".devpilot", "backups", rel_hash)
        if not os.path.exists(backup_dir):
            return {"backups": []}
        baks = sorted(glob.glob(os.path.join(backup_dir, "*.bak")))
        backups_list = []
        for b in baks:
            filename = os.path.basename(b)
            ts_str = filename.replace(".bak", "")
            try:
                ts = int(ts_str)
                backups_list.append({"timestamp": ts, "filename": filename})
            except ValueError:
                pass
        return {"backups": backups_list[::-1]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/files/flat")
def get_flat_files():
    if not workspace_state.root:
        return {"files": []}
    try:
        flat_list = []
        exclude_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', '.pytest_cache', '.devpilot'}
        exclude_files = {'.DS_Store'}
        for root, dirs, files in os.walk(workspace_state.root):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file in exclude_files:
                    continue
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, workspace_state.root).replace('\\', '/')
                flat_list.append(rel_path)
                if len(flat_list) >= 5000:
                    break
            if len(flat_list) >= 5000:
                break
        return {"files": flat_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

