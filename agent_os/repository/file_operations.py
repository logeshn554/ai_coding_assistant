import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

@dataclass
class FileOperationResult:
    success: bool
    message: str
    content: Optional[str] = None
    error: Optional[str] = None
    file_path: Optional[str] = None

class FileOperations:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)

    def resolve_path(self, file_path: str) -> str:
        """Convert relative path to absolute path within workspace."""
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(self.workspace_root, file_path)

    def read_file(self, file_path: str) -> FileOperationResult:
        """Read file content with proper error handling."""
        try:
            abs_path = self.resolve_path(file_path)
            
            # Validate path is within workspace
            if not os.path.abspath(abs_path).startswith(os.path.abspath(self.workspace_root)):
                return FileOperationResult(
                    success=False,
                    message="Security violation: path outside workspace",
                    error=f"Path {file_path} is outside workspace"
                )
            
            if not os.path.exists(abs_path):
                return FileOperationResult(
                    success=False,
                    message=f"File not found: {file_path}",
                    error="File does not exist"
                )
            
            if not os.path.isfile(abs_path):
                return FileOperationResult(
                    success=False,
                    message=f"Path is not a file: {file_path}",
                    error="Path is a directory, not a file"
                )
            
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            self.logger.info(f"Successfully read file: {file_path} ({len(content)} bytes)")
            return FileOperationResult(
                success=True,
                message=f"Read {len(content)} bytes",
                content=content,
                file_path=file_path
            )
            
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {str(e)}")
            return FileOperationResult(
                success=False,
                message=f"Error reading file: {str(e)}",
                error=str(e)
            )

    def write_file(self, file_path: str, content: str) -> FileOperationResult:
        """Write file content with atomic operations."""
        try:
            abs_path = self.resolve_path(file_path)
            
            # Validate path
            if not os.path.abspath(abs_path).startswith(os.path.abspath(self.workspace_root)):
                return FileOperationResult(
                    success=False,
                    message="Security violation: path outside workspace",
                    error=f"Path {file_path} is outside workspace"
                )
            
            # Create directories
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            # Atomic write
            import tempfile
            dir_name = os.path.dirname(abs_path) or "."
            with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False, encoding='utf-8') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            os.replace(tmp_path, abs_path)
            self.logger.info(f"Successfully wrote file: {file_path} ({len(content)} bytes)")
            
            return FileOperationResult(
                success=True,
                message=f"Wrote {len(content)} bytes",
                file_path=file_path
            )
            
        except Exception as e:
            self.logger.error(f"Error writing file {file_path}: {str(e)}")
            return FileOperationResult(
                success=False,
                message=f"Error writing file: {str(e)}",
                error=str(e)
            )

    def create_file(self, file_path: str, content: str = "") -> FileOperationResult:
        """Create new file."""
        try:
            abs_path = self.resolve_path(file_path)
            
            if os.path.exists(abs_path):
                return FileOperationResult(
                    success=False,
                    message=f"File already exists: {file_path}",
                    error="File exists"
                )
            
            return self.write_file(file_path, content)
            
        except Exception as e:
            self.logger.error(f"Error creating file {file_path}: {str(e)}")
            return FileOperationResult(
                success=False,
                message=f"Error creating file: {str(e)}",
                error=str(e)
            )

    def edit_file(self, file_path: str, target: str, replacement: str) -> FileOperationResult:
        """Edit file by replacing target text."""
        try:
            # Read current content
            read_result = self.read_file(file_path)
            if not read_result.success:
                return read_result
            
            current_content = read_result.content
            if current_content is None:
                return FileOperationResult(
                    success=False,
                    message="File content is empty or unreadable",
                    error="Unreadable content"
                )
            
            if target not in current_content:
                return FileOperationResult(
                    success=False,
                    message="Target text not found in file",
                    error=f"Cannot find target text in {file_path}"
                )
            
            # Replace
            new_content = current_content.replace(target, replacement, 1)
            
            # Write back
            return self.write_file(file_path, new_content)
            
        except Exception as e:
            self.logger.error(f"Error editing file {file_path}: {str(e)}")
            return FileOperationResult(
                success=False,
                message=f"Error editing file: {str(e)}",
                error=str(e)
            )

    def delete_file(self, file_path: str) -> FileOperationResult:
        """Delete a file."""
        try:
            abs_path = self.resolve_path(file_path)
            
            if not os.path.exists(abs_path):
                return FileOperationResult(
                    success=False,
                    message=f"File not found: {file_path}",
                    error="File does not exist"
                )
            
            os.remove(abs_path)
            self.logger.info(f"Successfully deleted file: {file_path}")
            
            return FileOperationResult(
                success=True,
                message="File deleted",
                file_path=file_path
            )
            
        except Exception as e:
            self.logger.error(f"Error deleting file {file_path}: {str(e)}")
            return FileOperationResult(
                success=False,
                message=f"Error deleting file: {str(e)}",
                error=str(e)
            )

    def list_files_in_dir(self, dir_path: str = "") -> FileOperationResult:
        """List files in directory."""
        try:
            abs_path = self.resolve_path(dir_path) if dir_path else self.workspace_root
            
            if not os.path.isdir(abs_path):
                return FileOperationResult(
                    success=False,
                    message=f"Directory not found: {dir_path}",
                    error="Path is not a directory"
                )
            
            files = []
            for root, dirs, filenames in os.walk(abs_path):
                dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "dist", "build", "venv", ".venv"}]
                for f in filenames:
                    rel_path = os.path.relpath(os.path.join(root, f), self.workspace_root)
                    files.append(rel_path.replace("\\", "/"))
            
            return FileOperationResult(
                success=True,
                message=f"Found {len(files)} files",
                content="\n".join(files),
                file_path=dir_path
            )
            
        except Exception as e:
            self.logger.error(f"Error listing directory {dir_path}: {str(e)}")
            return FileOperationResult(
                success=False,
                message=f"Error listing directory: {str(e)}",
                error=str(e)
            )
