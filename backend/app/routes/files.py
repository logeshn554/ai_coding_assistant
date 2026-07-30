import os
import shutil
import hashlib
import glob
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
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
async def get_files(path: str = ""):
    try:
        if not workspace_state.root:
            return []
        return await asyncio.to_thread(list_workspace_dir, workspace_state.root, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/files/content")
async def get_file_content(path: str):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        content = await asyncio.to_thread(read_workspace_file, workspace_state.root, path)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _create_file_sync(root: str, path: str, is_dir: bool):
    abs_path = safe_path(root, path)
    if is_dir:
        os.makedirs(abs_path, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        if not os.path.exists(abs_path):
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write("")

@router.post("/api/files/create")
async def create_file(req: FileCreateRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        await asyncio.to_thread(_create_file_sync, workspace_state.root, req.path, req.is_dir)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/save")
async def save_file(req: FileSaveRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        await asyncio.to_thread(write_workspace_file, workspace_state.root, req.path, req.content)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/files/delete")
async def delete_file(req: FileDeleteRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        await asyncio.to_thread(delete_workspace_item, workspace_state.root, req.path)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _rename_file_sync(root: str, old_path: str, new_path: str):
    abs_old = safe_path(root, old_path)
    abs_new = safe_path(root, new_path)
    os.makedirs(os.path.dirname(abs_new), exist_ok=True)
    shutil.move(abs_old, abs_new)

@router.post("/api/files/rename")
async def rename_file(req: FileRenameRequest):
    try:
        if not workspace_state.root:
            raise HTTPException(status_code=400, detail="No workspace folder open.")
        await asyncio.to_thread(_rename_file_sync, workspace_state.root, req.old_path, req.new_path)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/files/search")
async def get_codebase_search(query: str):
    try:
        if not workspace_state.root:
            return []
        return await asyncio.to_thread(search_workspace_codebase, workspace_state.root, query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/rollback")
async def rollback_file_endpoint(req: RollbackRequest):
    success = await asyncio.to_thread(rollback_file, workspace_state.root, req.path, req.timestamp)
    if not success:
        raise HTTPException(status_code=400, detail="No backup available for rollback or rollback failed.")
    return {"success": True}


def _get_file_backups_sync(root: str, path: str):
    rel_hash = hashlib.md5(path.encode("utf-8")).hexdigest()
    backup_dir = os.path.join(root, ".devpilot", "backups", rel_hash)
    if not os.path.exists(backup_dir):
        return []
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
    return backups_list[::-1]

@router.get("/api/files/backups")
async def get_file_backups(path: str):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        backups_list = await asyncio.to_thread(_get_file_backups_sync, workspace_state.root, path)
        return {"backups": backups_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_flat_files_sync(root: str) -> list[str]:
    flat_list = []
    exclude_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', '.pytest_cache', '.devpilot'}
    exclude_files = {'.DS_Store'}
    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file in exclude_files:
                continue
            abs_path = os.path.join(root_dir, file)
            rel_path = os.path.relpath(abs_path, root).replace('\\', '/')
            flat_list.append(rel_path)
            if len(flat_list) >= 5000:
                break
        if len(flat_list) >= 5000:
            break
    return flat_list

@router.get("/api/files/flat")
async def get_flat_files():
    if not workspace_state.root:
        return {"files": []}
    try:
        flat_list = await asyncio.to_thread(_get_flat_files_sync, workspace_state.root)
        return {"files": flat_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _save_uploaded_file(file_src, target_path: str):
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file_src, buffer)

@router.post("/api/files/upload")
async def upload_attachment(file: UploadFile = File(...)):
    """Upload a file or pasted image attachment for AI Chat processing."""
    try:
        root = workspace_state.root or os.path.join(os.path.expanduser("~"), ".devpilot")
        att_dir = os.path.join(root, "artifacts", "attachments")
        await asyncio.to_thread(os.makedirs, att_dir, exist_ok=True)

        filename = os.path.basename(file.filename or "pasted_image.png")
        safe_filename = f"{hashlib.md5(filename.encode()).hexdigest()[:8]}_{filename}"
        target_path = os.path.abspath(os.path.join(att_dir, safe_filename))

        # Defense-in-depth containment check
        if not target_path.startswith(os.path.abspath(att_dir)):
            raise HTTPException(status_code=400, detail="Path traversal attempt detected in filename.")

        await asyncio.to_thread(_save_uploaded_file, file.file, target_path)

        rel_path = os.path.relpath(target_path, workspace_state.root).replace("\\", "/") if workspace_state.root else target_path
        return {
            "success": True,
            "filename": filename,
            "path": target_path,
            "rel_path": rel_path
        }
    except Exception as e:
        logger.error(f"Failed to upload attachment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
