import os
import subprocess
from pathlib import Path

class WorkspaceIndex:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        # Cache maps relative_path -> {"mtime": float, "size": int, "first_lines": str}
        self.cache = {}

    def update(self):
        if not self.workspace_root or not os.path.isdir(self.workspace_root):
            return
            
        root_path = Path(self.workspace_root).resolve()
        
        text_extensions = {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", 
            ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".conf",
            ".sh", ".bat", ".dockerfile", "dockerfile"
        }
        
        exclude_dirs = {".git", "node_modules", "venv", ".devpilot", "__pycache__"}
        
        current_paths = set()
        
        for root, dirs, files in os.walk(str(root_path)):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                filepath = Path(root) / file
                ext = filepath.suffix.lower()
                name = filepath.name.lower()
                if ext in text_extensions or name == "dockerfile" or name == "makefile":
                    try:
                        rel_path = filepath.relative_to(root_path).as_posix()
                        current_paths.add(rel_path)
                        
                        stat = filepath.stat()
                        mtime = stat.st_mtime
                        size = stat.st_size
                        
                        cached = self.cache.get(rel_path)
                        if not cached or cached["mtime"] != mtime or cached["size"] != size:
                            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                                lines = []
                                for _ in range(50):
                                    line = f.readline()
                                    if not line:
                                        break
                                    lines.append(line)
                            
                            self.cache[rel_path] = {
                                "mtime": mtime,
                                "size": size,
                                "first_lines": "".join(lines)
                            }
                    except Exception:
                        pass
                        
        for deleted in list(self.cache.keys()):
            if deleted not in current_paths:
                del self.cache[deleted]

    def get_prompt_context(self, max_tokens: int = 2000) -> str:
        """
        Formats workspace context up to max_tokens.
        """
        self.update()
        if not self.cache:
            return ""
            
        max_chars = max_tokens * 4
        parts = ["\n=== Workspace Context (First 50 lines of project files) ==="]
        current_len = len(parts[0])
        
        for rel_path, data in sorted(self.cache.items()):
            file_header = f"\n\nFile: {rel_path}\n---\n"
            content = data["first_lines"]
            
            if current_len + len(file_header) + len(content) > max_chars:
                remaining = max_chars - current_len - len(file_header)
                if remaining > 50:
                    parts.append(file_header + content[:remaining] + "\n... [TRUNCATED due to token limit] ...")
                else:
                    parts.append("\n\n... [ADDITIONAL FILES TRUNCATED due to token limit] ...")
                break
                
            parts.append(file_header + content)
            current_len += len(file_header) + len(content)
            
        return "".join(parts)
