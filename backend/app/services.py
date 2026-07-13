import os
import logging
from .async_files import read_workspace_file

logger = logging.getLogger("devpilot.services")

class WorkspaceManager:
    """
    Coordinates repository workspace directories, settings, and path lookups.
    """
    def __init__(self, root: str = None):
        self._root = root or os.getcwd()

    @property
    def root(self) -> str:
        return self._root

    @root.setter
    def root(self, path: str):
        if path:
            self._root = os.path.abspath(path)
            logger.info(f"WorkspaceManager: Workspace root changed to {self._root}")

    def safe_path(self, relative_path: str) -> str:
        """
        Converts relative path to absolute path and asserts safe workspace confinement.
        """
        if not relative_path:
            return self._root
        abs_path = os.path.abspath(os.path.join(self._root, relative_path))
        if not abs_path.startswith(self._root):
            raise PermissionError(f"Access denied: path '{relative_path}' escapes workspace boundaries.")
        return abs_path


class ContextManager:
    """
    Manages active context files, tracking token length and potential overflow.
    """
    def __init__(self, max_tokens: int = 8192):
        self.max_tokens = max_tokens
        self.pinned_files = set()

    def add_file(self, relative_path: str):
        self.pinned_files.add(relative_path)

    def remove_file(self, relative_path: str):
        self.pinned_files.discard(relative_path)

    def clear(self):
        self.pinned_files.clear()

    async def get_payload(self, workspace: WorkspaceManager) -> tuple[str, int, bool]:
        """
        Retrieves formatted files payload, total estimated tokens, and warning flag.
        """
        formatted = []
        total_tokens = 0
        warning = False

        for file_path in sorted(list(self.pinned_files)):
            try:
                abs_path = workspace.safe_path(file_path)
                if os.path.exists(abs_path) and os.path.isfile(abs_path):
                    content = await read_workspace_file(workspace.root, file_path)
                    # Rough estimation: 4 chars = 1 token
                    tokens = len(content) // 4
                    if total_tokens + tokens > self.max_tokens * 0.9:
                        warning = True
                        logger.warning(f"ContextManager: Context buffer truncated for {file_path}")
                        break
                    total_tokens += tokens
                    formatted.append(f"--- FILE: {file_path} ---\n{content}\n")
            except Exception as e:
                logger.error(f"ContextManager: Failed to read context file {file_path}: {str(e)}")

        return "\n".join(formatted), total_tokens, warning
