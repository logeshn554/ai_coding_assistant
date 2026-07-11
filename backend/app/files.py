import os
import shutil
import re
import hashlib
import time
import glob
from .config import ConfigManager

config_manager = ConfigManager()

def safe_path(workspace_root: str, relative_path: str) -> str:
    """
    Resolves relative_path against workspace_root and ensures it doesn't escape the root.
    """
    if not relative_path:
        relative_path = "."
    
    # Normalize paths
    abs_root = os.path.realpath(workspace_root)
    # Join and normalize target
    abs_target = os.path.realpath(os.path.join(abs_root, relative_path))
    
    # Check if the target is within the root
    is_inside = False
    if os.name == "nt":
        is_inside = abs_target.lower().startswith(abs_root.lower())
    else:
        is_inside = abs_target.startswith(abs_root)
        
    if not is_inside:
        raise PermissionError(f"Access denied: path '{relative_path}' is outside the workspace root.")
    
    return abs_target

def list_workspace_dir(workspace_root: str, relative_path: str = "") -> list:
    """
    Lists the files and folders in the directory specified by relative_path.
    Returns metadata for each item.
    """
    target_dir = safe_path(workspace_root, relative_path)
    if not os.path.isdir(target_dir):
        raise FileNotFoundError(f"Directory '{relative_path}' not found.")
        
    items = []
    # Excluded directories for safety & performance
    exclude_dirs = set(config_manager.get_exclude_list())
    exclude_files = set()
    


    try:
        for entry in os.scandir(target_dir):
            if entry.name in exclude_dirs or entry.name in exclude_files:
                continue
                
            is_dir = entry.is_dir()
            # Calculate relative path from workspace root
            rel_path = os.path.relpath(entry.path, workspace_root).replace("\\", "/")
            
            items.append({
                "name": entry.name,
                "path": rel_path,
                "is_dir": is_dir,
                "size": entry.stat().st_size if not is_dir else 0,
                "mtime": entry.stat().st_mtime
            })
    except Exception as e:
        raise IOError(f"Failed to list directory: {str(e)}")
        
    # Sort: folders first, then files alphabetically
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return items

class FileCacheManager:
    def __init__(self):
        self.cache = {} # abs_path -> {"content": str, "mtime": float}

    def get(self, abs_path: str) -> str:
        if not os.path.exists(abs_path):
            return None
        try:
            mtime = os.path.getmtime(abs_path)
            if abs_path in self.cache and self.cache[abs_path]["mtime"] == mtime:
                return self.cache[abs_path]["content"]
        except Exception:
            pass
        return None

    def set(self, abs_path: str, content: str):
        try:
            mtime = os.path.getmtime(abs_path)
            self.cache[abs_path] = {"content": content, "mtime": mtime}
        except Exception:
            pass

file_cache = FileCacheManager()

def create_backup(workspace_root: str, relative_path: str) -> bool:
    if not config_manager.get_auto_backup_enabled():
        return False
    try:
        abs_path = safe_path(workspace_root, relative_path)
        if not os.path.exists(abs_path):
            return False
            
        # Define backup folder locally in .devpilot
        rel_hash = hashlib.md5(relative_path.encode("utf-8")).hexdigest()
        backup_dir = os.path.join(workspace_root, ".devpilot", "backups", rel_hash)
        os.makedirs(backup_dir, exist_ok=True)
        
        # Copy file with timestamp
        timestamp = int(time.time() * 1000)
        backup_path = os.path.join(backup_dir, f"{timestamp}.bak")
        
        # Save relative path metadata
        meta_path = os.path.join(backup_dir, "meta.txt")
        if not os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write(relative_path)
                
        shutil.copy2(abs_path, backup_path)
        
        # Limit backups to latest 10 copies
        backups = sorted(glob.glob(os.path.join(backup_dir, "*.bak")))
        if len(backups) > 10:
            for old_b in backups[:-10]:
                try:
                    os.remove(old_b)
                except Exception:
                    pass
        return True
    except Exception:
        return False

def rollback_file(workspace_root: str, relative_path: str, timestamp: int = None) -> bool:
    try:
        rel_hash = hashlib.md5(relative_path.encode("utf-8")).hexdigest()
        backup_dir = os.path.join(workspace_root, ".devpilot", "backups", rel_hash)
        if not os.path.exists(backup_dir):
            return False
            
        backups = sorted(glob.glob(os.path.join(backup_dir, "*.bak")))
        if not backups:
            return False
            
        if timestamp:
            latest_backup = os.path.join(backup_dir, f"{timestamp}.bak")
            if not os.path.exists(latest_backup):
                return False
        else:
            latest_backup = backups[-1]
        abs_path = safe_path(workspace_root, relative_path)
        
        # Create directories if they were deleted
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        shutil.copy2(latest_backup, abs_path)
        
        # Remove that backup file so subsequent rollback calls undo to previous states
        os.remove(latest_backup)
        
        # Invalidate cache
        if abs_path in file_cache.cache:
            file_cache.cache.pop(abs_path)
        return True
    except Exception:
        return False

def read_workspace_file(workspace_root: str, relative_path: str) -> str:
    """
    Reads the content of a file in the workspace (using in-memory mtime cache).
    """
    target_file = safe_path(workspace_root, relative_path)
    if not os.path.isfile(target_file):
        raise FileNotFoundError(f"File '{relative_path}' not found.")
        
    # Check cache first
    cached_content = file_cache.get(target_file)
    if cached_content is not None:
        return cached_content
        
    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            file_cache.set(target_file, content)
            return content
    except Exception as e:
        raise IOError(f"Failed to read file: {str(e)}")

def write_workspace_file(workspace_root: str, relative_path: str, content: str) -> None:
    """
    Writes content to a file in the workspace. Creates parent directories and backups first.
    """
    target_file = safe_path(workspace_root, relative_path)
    
    try:
        # Create backup if file exists before overwriting
        if os.path.exists(target_file):
            create_backup(workspace_root, relative_path)
            
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Update cache
        file_cache.set(target_file, content)
    except Exception as e:
        raise IOError(f"Failed to write file: {str(e)}")

def delete_workspace_item(workspace_root: str, relative_path: str) -> None:
    """
    Deletes a file or directory in the workspace.
    """
    target_path = safe_path(workspace_root, relative_path)
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Item '{relative_path}' not found.")
        
    try:
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)
    except Exception as e:
        raise IOError(f"Failed to delete item: {str(e)}")

def search_workspace_codebase(workspace_root: str, query: str) -> list:
    """
    Simple grep-like search across files in the workspace.
    Excludes binary files, .git, node_modules, etc.
    """
    results = []
    exclude_dirs = set(config_manager.get_exclude_list())
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}
    
    # If query is empty or whitespace, return empty results
    if not query or not query.strip():
        return []
    
    # Compile regex case-insensitively
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        # If query is not a valid regex, match literally
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    for root, dirs, files in os.walk(workspace_root):
        # Prune excluded directories
        current_excludes = set(exclude_dirs)
        dirs[:] = [d for d in dirs if d not in current_excludes]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in exclude_extensions:
                continue
                
            abs_file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(abs_file_path, workspace_root).replace("\\", "/")
            
            try:
                with open(abs_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            results.append({
                                "path": rel_file_path,
                                "line": line_num,
                                "content": line.strip()
                            })
                            if len(results) >= 100:  # limit to 100 results
                                return results
            except Exception:
                # Skip files that can't be read (e.g. permission error, binary encoding issue)
                continue
                
    return results

def get_codebase_contents(workspace_root: str) -> str:
    """
    Scans the codebase and returns a formatted string containing the names, relative paths,
    and entire content of all source code files in the workspace (excluding binary/excluded directories).
    """
    exclude_dirs = {".git", "node_modules", "venv", "__pycache__", ".devpilot", "dist", "build"}
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}
    
    is_editor_root = False
    try:
        is_editor_root = (
            os.path.isdir(os.path.join(workspace_root, "backend", "app")) and
            os.path.isdir(os.path.join(workspace_root, "frontend", "src"))
        )
    except Exception:
        pass

    output_lines = []
    
    for root, dirs, files in os.walk(workspace_root):
        # Prune excluded directories
        current_excludes = set(exclude_dirs)
        if is_editor_root and root == os.path.realpath(workspace_root):
            current_excludes.update({"frontend", "backend", "venv"})
            
        dirs[:] = [d for d in dirs if d not in current_excludes]
        
        # If we are in the root of the editor, filter out editor files
        if is_editor_root and os.path.realpath(root) == os.path.realpath(workspace_root):
            files = [f for f in files if f not in {"requirements.txt", "run.py", "README.md"}]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in exclude_extensions:
                continue
                
            abs_file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(abs_file_path, workspace_root).replace("\\", "/")
            
            try:
                # Read content
                with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                
                file_chunk = (
                    f"===================================================\n"
                    f"File: {rel_file_path}\n"
                    f"===================================================\n"
                    f"{content}\n\n"
                )
                
                # Check limit (1MB max text payload)
                if len("".join(output_lines)) + len(file_chunk) > 1000000:
                    output_lines.append(f"\n[Truncated: Codebase exceeds 1MB limit]\n")
                    break
                    
                output_lines.append(file_chunk)
            except Exception:
                continue
                
    return "".join(output_lines)

import asyncio

async def async_read_workspace_file(workspace_root: str, relative_path: str) -> str:
    return await asyncio.to_thread(read_workspace_file, workspace_root, relative_path)

async def async_write_workspace_file(workspace_root: str, relative_path: str, content: str) -> None:
    return await asyncio.to_thread(write_workspace_file, workspace_root, relative_path, content)

async def async_search_workspace_codebase(workspace_root: str, query: str) -> list:
    return await asyncio.to_thread(search_workspace_codebase, workspace_root, query)

async def async_get_codebase_contents(workspace_root: str) -> str:
    return await asyncio.to_thread(get_codebase_contents, workspace_root)


