import glob
import hashlib
import logging
import os
import re
import shutil
import subprocess
import time

from .config import config_manager

logger = logging.getLogger("loopix.files")

def safe_path(workspace_root: str, relative_path: str) -> str:
    """
    Resolves relative_path against workspace_root using SecureFileSystem canonical validation.
    """
    from .agent.security.secure_fs import SecureFileSystem
    sfs = SecureFileSystem(workspace_root)
    return sfs.resolve_safe_path(relative_path or ".")

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
        raise OSError(f"Failed to list directory: {e!s}")
        
    # Sort: folders first, then files alphabetically
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return items

class FileCacheManager:
    def __init__(self):
        self.cache = {} # (abs_path, limit) -> {"content": str, "mtime": float}

    def get(self, abs_path: str, limit: int) -> str | None:
        if not os.path.exists(abs_path):
            return None
        try:
            mtime = os.path.getmtime(abs_path)
            key = (abs_path, limit)
            if key in self.cache and self.cache[key]["mtime"] == mtime:
                return self.cache[key]["content"]
        except Exception:
            pass
        return None

    def set(self, abs_path: str, limit: int, content: str):
        try:
            mtime = os.path.getmtime(abs_path)
            key = (abs_path, limit)
            self.cache[key] = {"content": content, "mtime": mtime}
            if len(self.cache) > 200:
                first_key = next(iter(self.cache))
                self.cache.pop(first_key, None)
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
            
        # Define backup folder locally in .loopix
        rel_hash = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
        backup_dir = os.path.join(workspace_root, ".loopix", "backups", rel_hash)
        os.makedirs(backup_dir, exist_ok=True)
        
        # Copy file with timestamp
        timestamp = int(time.time() * 1000)
        backup_path = os.path.join(backup_dir, f"{timestamp}.bak")
        
        # Save relative path metadata atomically to prevent truncation risk
        meta_path = os.path.join(backup_dir, "meta.txt")
        if not os.path.exists(meta_path):
            tmp_meta_path = meta_path + ".tmp"
            try:
                with open(tmp_meta_path, "w", encoding="utf-8") as f:
                    f.write(relative_path)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_meta_path, meta_path)
            except Exception as e:
                logger.warning("Failed atomic backup meta write: %s", e)
                if os.path.exists(tmp_meta_path):
                    try:
                        os.remove(tmp_meta_path)
                    except Exception:
                        pass
                
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
        rel_hash = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
        backup_dir = os.path.join(workspace_root, ".loopix", "backups", rel_hash)
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
        keys_to_pop = [k for k in file_cache.cache if k[0] == abs_path]
        for k in keys_to_pop:
            file_cache.cache.pop(k, None)
        from .workspace_index import WorkspaceIndex
        WorkspaceIndex.mark_dirty(workspace_root)
        return True
    except Exception:
        return False

def read_workspace_file(workspace_root: str, relative_path: str, max_chars: int | None = None) -> str:
    """
    Reads the content of a file in the workspace (using in-memory mtime cache).
    """
    from .context_config import READ_FILE_MAX_CHARS
    limit = max_chars or READ_FILE_MAX_CHARS
    
    target_file = safe_path(workspace_root, relative_path)
    if not os.path.isfile(target_file):
        raise FileNotFoundError(f"File '{relative_path}' not found.")
        
    # Check cache first
    cached_content = file_cache.get(target_file, limit)
    if cached_content is not None:
        return cached_content
        
    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(limit + 1)
            
        if len(content) <= limit:
            file_cache.set(target_file, limit, content)
            return content
            
        # Truncation occurred
        byte_size = os.path.getsize(target_file)
        notice = f"\n\n[file '{relative_path}' truncated after {limit} characters; more content remains (file size: {byte_size} bytes)]\n\n"
        truncated_content = content[:limit]
        if limit > 200:
            nl_idx = truncated_content.rstrip().rfind('\n', limit - 200, limit)
            if nl_idx != -1:
                truncated_content = truncated_content[:nl_idx + 1]
                
        result = f"{truncated_content.rstrip()}{notice}"
        file_cache.set(target_file, limit, result)
        return result
    except Exception as e:
        raise OSError(f"Failed to read file: {e!s}")

def read_workspace_file_range(
    workspace_root: str,
    relative_path: str,
    start_line: int,
    end_line: int,
    max_chars: int | None = None,
) -> str:
    """
    Reads a specific line range from a file, bounded by line numbers and max_chars limit.
    """
    from .context_config import READ_FILE_MAX_CHARS
    limit = max_chars or READ_FILE_MAX_CHARS

    if start_line < 1:
        raise ValueError(f"start_line must be >= 1, got {start_line}")
    if end_line < start_line:
        raise ValueError(f"end_line ({end_line}) must be >= start_line ({start_line})")

    target_file = safe_path(workspace_root, relative_path)
    if not os.path.isfile(target_file):
        raise FileNotFoundError(f"File '{relative_path}' not found.")

    output_lines = []
    current_char_count = 0
    truncation_occurred = False

    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, 1):
                if idx < start_line:
                    continue
                if idx > end_line:
                    break
                
                formatted_line = f"{idx}: {line}"
                line_len = len(formatted_line)
                if current_char_count + line_len > limit:
                    truncation_occurred = True
                    break
                output_lines.append(formatted_line)
                current_char_count += line_len

        result_content = "".join(output_lines)
        if truncation_occurred:
            byte_size = os.path.getsize(target_file)
            notice = f"\n\n[file '{relative_path}' range {start_line}-{end_line} truncated after {limit} characters; more lines remain (file size: {byte_size} bytes)]\n\n"
            result_content = f"{result_content.rstrip()}{notice}"
        return result_content
    except Exception as e:
        raise OSError(f"Failed to read file range: {e!s}")

def search_workspace_file(
    workspace_root: str,
    relative_path: str,
    query: str,
    max_matches: int = 20,
    context_lines: int = 3,
) -> str:
    """
    Searches a workspace file for occurrences of query and returns matching lines with surrounding context.
    """
    target_file = safe_path(workspace_root, relative_path)
    if not os.path.isfile(target_file):
        raise FileNotFoundError(f"File '{relative_path}' not found.")

    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            
        matches = []
        query_lower = query.lower()
        for idx, line in enumerate(lines):
            if query_lower in line.lower():
                matches.append(idx)
                if len(matches) >= max_matches:
                    break
                    
        if not matches:
            return f"No matches found for '{query}' in {relative_path}"
            
        output = []
        last_end = -1
        for m_idx in matches:
            start = max(0, m_idx - context_lines)
            end = min(len(lines) - 1, m_idx + context_lines)
            
            if last_end != -1 and start <= last_end:
                start = last_end + 1
                
            if start > 0 and last_end != -1 and start > last_end + 1:
                output.append("...\n")
                
            for idx in range(start, end + 1):
                output.append(f"{idx + 1}: {lines[idx]}")
                
            last_end = end
            
        return "".join(output)
    except Exception as e:
        raise OSError(f"Failed to search file: {e!s}")

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
        import uuid
        tmp_file = f"{target_file}.tmp_{uuid.uuid4().hex[:8]}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, target_file)
            
        # Invalidate cache keys for target_file
        keys_to_pop = [k for k in file_cache.cache if k[0] == target_file]
        for k in keys_to_pop:
            file_cache.cache.pop(k, None)
        from .workspace_index import WorkspaceIndex
        WorkspaceIndex.mark_dirty(workspace_root)
    except Exception as e:
        raise OSError(f"Failed to write file: {e!s}")

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
        from .workspace_index import WorkspaceIndex
        WorkspaceIndex.mark_dirty(workspace_root)
    except Exception as e:
        raise OSError(f"Failed to delete item: {e!s}")

def _search_with_ripgrep(workspace_root: str, query: str) -> list | None:
    """
    Executes ripgrep subprocess with --json formatting if rg executable exists.
    Returns list of match dicts or None on failure to trigger python fallback.
    """
    rg_path = shutil.which("rg")
    if not rg_path:
        return None
    try:
        cmd = [rg_path, "--json", "-i", "-m", "100", "--", query, workspace_root]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
        if res.returncode not in (0, 1):
            return None

        results = []
        import json
        for line in res.stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    payload = data.get("data", {})
                    path_obj = payload.get("path", {})
                    raw_path = path_obj.get("text", "")
                    rel_p = os.path.relpath(raw_path, workspace_root).replace("\\", "/")
                    line_num = payload.get("line_number", 1)
                    lines_obj = payload.get("lines", {})
                    content = lines_obj.get("text", "").strip()
                    results.append({
                        "path": rel_p,
                        "line": line_num,
                        "content": content
                    })
                    if len(results) >= 100:
                        break
            except Exception:
                continue
        return results
    except Exception:
        return None


def search_workspace_codebase(
    workspace_root: str,
    query: str,
    case_sensitive: bool = False,
    whole_word: bool = False,
    is_regex: bool = False
) -> list:
    """
    Grep-like search across files in the workspace with support for Case-sensitive, Whole-word, and Regex matching.
    Excludes binary files, .git, node_modules, etc.
    """
    if not query or not query.strip():
        return []

    # If simple search and rg is available, try ripgrep
    if not case_sensitive and not whole_word and not is_regex:
        rg_results = _search_with_ripgrep(workspace_root, query)
        if rg_results is not None:
            return rg_results

    results = []
    exclude_dirs = set(config_manager.get_exclude_list())
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}
    
    # Build regex pattern
    raw_pattern = query if is_regex else re.escape(query)
    if whole_word:
        raw_pattern = rf"\b{raw_pattern}\b"
    
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(raw_pattern, flags)
    except re.error:
        pattern = re.compile(re.escape(query), flags)

    for root, dirs, files in os.walk(workspace_root):
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
                            if len(results) >= 200:
                                return results
            except Exception:
                continue
                
    return results

def replace_workspace_codebase(
    workspace_root: str,
    query: str,
    replace_text: str,
    case_sensitive: bool = False,
    whole_word: bool = False,
    is_regex: bool = False,
    target_paths: list[str] | None = None
) -> dict:
    """
    Finds and replaces text across workspace files safely with automatic file backups.
    """
    if not query:
        return {"modified_files": 0, "total_replacements": 0}

    raw_pattern = query if is_regex else re.escape(query)
    if whole_word:
        raw_pattern = rf"\b{raw_pattern}\b"
    
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(raw_pattern, flags)
    except re.error:
        pattern = re.compile(re.escape(query), flags)

    modified_files = 0
    total_replacements = 0
    exclude_dirs = set(config_manager.get_exclude_list())
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}

    for root, dirs, files in os.walk(workspace_root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in exclude_extensions:
                continue
                
            abs_file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(abs_file_path, workspace_root).replace("\\", "/")
            
            if target_paths and rel_file_path not in target_paths:
                continue
                
            try:
                with open(abs_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                new_content, count = pattern.subn(replace_text, content)
                if count > 0:
                    write_workspace_file(workspace_root, rel_file_path, new_content)
                    modified_files += 1
                    total_replacements += count
            except Exception:
                continue

    return {"modified_files": modified_files, "total_replacements": total_replacements}


def get_codebase_contents(workspace_root: str, max_chars: int | None = None) -> str:
    """
    Scans the codebase and returns a formatted string containing the names, relative paths,
    and entire content of all source code files in the workspace (excluding binary/excluded directories).
    """
    from .context_config import CODEBASE_SCAN_MAX_CHARS
    limit = max_chars or CODEBASE_SCAN_MAX_CHARS
    
    exclude_dirs = {".git", "node_modules", "venv", "__pycache__", ".loopix", "dist", "build"}
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}
    
    is_editor_root = False
    try:
        is_editor_root = (
            os.path.isdir(os.path.join(workspace_root, "backend", "app")) and
            os.path.isdir(os.path.join(workspace_root, "frontend", "src"))
        )
    except Exception:
        pass

    output_parts = []
    current_total_chars = 0
    truncated = False
    
    for root, dirs, files in os.walk(workspace_root):
        if current_total_chars >= limit:
            truncated = True
            break
            
        current_excludes = set(exclude_dirs)
        if is_editor_root and root == os.path.realpath(workspace_root):
            current_excludes.update({"frontend", "backend", "venv"})
            
        dirs[:] = [d for d in dirs if d not in current_excludes]
        
        if is_editor_root and os.path.realpath(root) == os.path.realpath(workspace_root):
            files = [f for f in files if f not in {"requirements.txt", "run.py", "README.md"}]

        for file in files:
            if current_total_chars >= limit:
                truncated = True
                break
                
            ext = os.path.splitext(file)[1].lower()
            if ext in exclude_extensions:
                continue
                
            abs_file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(abs_file_path, workspace_root).replace("\\", "/")
            
            try:
                file_size = os.path.getsize(abs_file_path)
                if current_total_chars + file_size > limit:
                    truncated = True
                    remaining_budget = limit - current_total_chars
                    if remaining_budget > 100:
                        with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read(remaining_budget)
                        file_chunk = (
                            f"===================================================\n"
                            f"File: {rel_file_path} (truncated)\n"
                            f"===================================================\n"
                            f"{content}\n\n"
                        )
                        output_parts.append(file_chunk)
                        current_total_chars += len(file_chunk)
                    break
                
                with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                
                file_chunk = (
                    f"===================================================\n"
                    f"File: {rel_file_path}\n"
                    f"===================================================\n"
                    f"{content}\n\n"
                )
                output_parts.append(file_chunk)
                current_total_chars += len(file_chunk)
            except Exception:
                continue
                
    result = "".join(output_parts)
    if truncated:
        result += f"\n[codebase scan truncated at {limit} characters; some folders not scanned]\n"
    return result

def scan_workspace_for_bugs(workspace_root: str) -> str:
    """
    Executes the 'scan_for_bugs' tool on the given workspace and returns a concise bug report.
    """
    try:
        from .tools.scan_for_bugs import generate_bug_report_sync
        return generate_bug_report_sync()
    except Exception as e:
        return f"Bug scan failed: {e}"